package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"path"

	goredis "github.com/go-redis/redis"
	"github.com/google/uuid"
	_ "github.com/lib/pq"
	"github.com/vaughan0/go-ini"
)

type KeyCache struct {
	UserId   int    `json:"user_id"`
	Username string `json:"username"`
}

// We don't need everything, so we don't include everything.
type MetaUser struct {
	Username string `json:"name"`
}

// We don't need everything, so we don't include everything.
type MetaSSHKey struct {
	Id          int      `json:"id"`
	Fingerprint string   `json:"fingerprint"`
	Key         string   `json:"key"`
	Owner       MetaUser `json:"owner"`
}

// Stores the SSH key in the database and returns the user's ID.
func storeKey(logger *log.Logger, db *sql.DB, key *MetaSSHKey) int {
	logger.Println("Storing meta.sr.ht key in git.sr.ht database")

	// Getting the user ID is really a separate concern, but this saves us a
	// SQL roundtrip and this is a performance-critical section
	query, err := db.Prepare(`
		WITH key_owner AS (
			SELECT id user_id
			FROM "user"
			WHERE "user".username = $1
		)
		INSERT INTO sshkey (
			user_id,
			meta_id,
			key,
			fingerprint
		)
		SELECT user_id, $2, $3, $4
		FROM key_owner
		-- This no-ops on conflict, but we still need this query to complete so
		-- that we can extract the user ID. DO NOTHING returns zero rows.
		ON CONFLICT (meta_id) DO UPDATE SET meta_id = $2
		RETURNING id, user_id;
	`)
	if err != nil {
		logger.Printf("Failed to prepare key insertion statement: %v", err)
		return 0
	}
	defer query.Close()

	var (
		userId int
		keyId  int
	)
	if err = query.QueryRow(key.Owner.Username,
		key.Id, key.Key, key.Fingerprint).Scan(&keyId, &userId); err != nil {

		logger.Printf("Error inserting key: %v", err)
	}

	logger.Printf("Stored key %d for user %d", keyId, userId)
	return userId
}

func fetchKeysFromMeta(logger *log.Logger, config ini.File,
	redis *goredis.Client, b64key string) (string, int) {

	meta, ok := config.Get("meta.sr.ht", "internal-origin")
	if !ok {
		meta, ok = config.Get("meta.sr.ht", "origin")
	}
	if !ok && meta == "" {
		logger.Fatalf("No origin configured for meta.sr.ht")
	}

	resp, err := http.Get(fmt.Sprintf("%s/api/ssh-key/%s", meta, b64key))
	if err != nil {
		logger.Printf("meta.sr.ht http.Get: %v", err)
		return "", 0
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		logger.Printf("non-200 response from meta.sr.ht: %d", resp.StatusCode)
		return "", 0
	}

	body, err := ioutil.ReadAll(resp.Body)
	var key MetaSSHKey
	if err = json.Unmarshal(body, &key); err != nil {
		return "", 0
	}

	// We wait to connect to postgres until we know we must
	pgcs, ok := config.Get("git.sr.ht", "connection-string")
	if !ok {
		logger.Fatalf("No connection string configured for git.sr.ht: %v", err)
	}
	db, err := sql.Open("postgres", pgcs)
	if err != nil {
		logger.Fatalf("Failed to open a database connection: %v", err)
	}
	userId := storeKey(logger, db, &key)
	logger.Println("Fetched key from meta.sr.ht")

	// Cache in Redis too
	cacheKey := fmt.Sprintf("git.sr.ht.ssh-keys.%s", b64key)
	cache := KeyCache{
		UserId:   userId,
		Username: key.Owner.Username,
	}
	cacheBytes, err := json.Marshal(&cache)
	if err != nil {
		logger.Printf("Caching SSH key in redis failed: %v", err)
	} else {
		redis.Set(cacheKey, cacheBytes, 0)
	}

	return key.Owner.Username, userId
}

func main() {
	// gitsrht-keys is run by sshd to generate an authorized_key file on stdout.
	// In order to facilitate this, we do one of two things:
	// - Attempt to fetch the cached key info from Redis (preferred)
	// - Fetch the key from meta.sr.ht and store it in SQL and Redis (slower)

	var (
		config ini.File
		err    error
		logger *log.Logger
	)
	// TODO: update key last used timestamp on meta.sr.ht

	redisHost, ok := config.Get("sr.ht", "redis-host")
	if !ok {
		redisHost = "localhost:6379"
	}
	redis := goredis.NewClient(&goredis.Options{Addr: redisHost})

	logf, err := os.OpenFile("/var/log/gitsrht-keys",
		os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0644)
	if err != nil {
		log.Printf("Warning: unable to open log file: %v "+
			"(using stderr instead)", err)
		logger = log.New(os.Stderr, "", log.LstdFlags)
	} else {
		logger = log.New(logf, "", log.LstdFlags)
	}

	for _, path := range []string{"../config.ini", "/etc/sr.ht/config.ini"} {
		config, err = ini.LoadFile(path)
		if err == nil {
			break
		}
	}
	if err != nil {
		logger.Fatalf("Failed to load config file: %v", err)
	}

	if len(os.Args) < 5 {
		logger.Fatalf("Expected four arguments from SSH")
	}
	logger.Printf("os.Args: %v", os.Args)
	keyType := os.Args[3]
	b64key := os.Args[4]

	var (
		username string
		userId   int
	)
	cacheKey := fmt.Sprintf("git.sr.ht.ssh-keys.%s", b64key)
	logger.Printf("Cache key for SSH key lookup: %s", cacheKey)
	cacheBytes, err := redis.Get(cacheKey).Bytes()
	if err != nil {
		logger.Println("Cache miss, going to meta.sr.ht")
		username, userId = fetchKeysFromMeta(logger, config, redis, b64key)
	} else {
		var cache KeyCache
		if err = json.Unmarshal(cacheBytes, &cache); err != nil {
			logger.Fatalf("Unmarshal cache JSON: %v", err)
		}
		userId = cache.UserId
		username = cache.Username
		logger.Printf("Cache hit: %d %s", userId, username)
	}

	if username == "" {
		logger.Println("Unknown public key")
		os.Exit(0)
	}

	defaultShell := path.Join(path.Dir(os.Args[0]), "gitsrht-shell")
	shell, ok := config.Get("git.sr.ht", "shell")
	if !ok {
		shell = defaultShell
	}

	push := uuid.New()
	logger.Printf("Assigned uuid %s to this push", push.String())
	shellCommand := fmt.Sprintf("%s '%d' '%s' '%s'",
		shell, userId, username, b64key)
	fmt.Printf(`restrict,command="%s",`+
		`environment="SRHT_PUSH=%s" %s %s %s`+"\n",
		shellCommand, push.String(), keyType, b64key, username)
}
