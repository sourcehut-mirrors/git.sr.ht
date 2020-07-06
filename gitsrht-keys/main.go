package main

import (
	"log"
	"os"
	"path"

	goredis "github.com/go-redis/redis"
	"github.com/vaughan0/go-ini"
	"git.sr.ht/~sircmpwn/scm.sr.ht/srht-keys"
)

func main() {
	// gitsrht-keys is run by sshd to generate an authorized_key file on stdout.
	// In order to facilitate this, we do one of two things:
	// - Attempt to fetch the cached key info from Redis (preferred)
	// - Fetch the key from meta.sr.ht and store it in SQL and Redis (slower)
	service := "git.sr.ht"
	shellName := "gitsrht-shell"
	logFile := "/var/log/gitsrht-keys"

	var (
		config   ini.File
		err      error
		logger   *log.Logger
		username string
		userId   int
		b64key   string
		keyType  string
		prefix   string
	)
	// TODO: update key last used timestamp on meta.sr.ht

	logf, err := os.OpenFile(logFile,
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

	redisHost, _ := config.Get("sr.ht", "redis-host")
	if redisHost == "" {
		redisHost = "redis://localhost:6379"
	}
	ropts, err := goredis.ParseURL(redisHost)
	if err != nil {
		logger.Fatalf("Failed to parse redis host: %v", err)
	}
	redis := goredis.NewClient(ropts)

	keyType, b64key, prefix, err = srhtkeys.ParseArgs(logger)
	if err != nil {
		os.Exit(0)
	}

	username, userId = srhtkeys.UserFromKey(logger, config, redis, service, b64key)

	if username == "" {
		logger.Println("Unknown public key")
		os.Exit(0)
	}

	defaultShell := path.Join(prefix, shellName)
	shell, ok := config.Get(service, "shell")
	if !ok {
		shell = defaultShell
	}

	srhtkeys.RenderAuthorizedKeysEntry(logger, shell, userId, username,
		b64key, keyType)
}
