package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	gopath "path"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"

	"github.com/google/shlex"
	_ "github.com/lib/pq"
	"github.com/vaughan0/go-ini"
)

const (
	ACCESS_NONE   = 0
	ACCESS_READ   = 1
	ACCESS_WRITE  = 2
	ACCESS_MANAGE = 4
)

func main() {
	var (
		config ini.File
		err    error
		logger *log.Logger

		pusherId   int
		pusherName string

		origin         string
		repos          string
		siteOwnerName  string
		siteOwnerEmail string
		postUpdate     string

		cmdstr string
		cmd    []string
	)

	log.SetFlags(0)
	logf, err := os.OpenFile("/var/log/gitsrht-shell",
		os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0644)
	if err != nil {
		log.Printf("Warning: unable to open log file: %v "+
			"(using stderr instead)", err)
		logger = log.New(os.Stderr, "", log.LstdFlags)
	} else {
		logger = log.New(logf, "", log.LstdFlags)
	}

	if len(os.Args) < 3 {
		logger.Fatalf("Expected two arguments from SSH")
	}
	logger.Printf("os.Args: %v", os.Args)

	if pusherId, err = strconv.Atoi(os.Args[1]); err != nil {
		logger.Fatalf("Couldn't interpret user ID: %v", err)
	}
	pusherName = os.Args[2]

	for _, path := range []string{"../config.ini", "/etc/sr.ht/config.ini"} {
		config, err = ini.LoadFile(path)
		if err == nil {
			break
		}
	}
	if err != nil {
		logger.Fatalf("Failed to load config file: %v", err)
	}

	origin, ok := config.Get("git.sr.ht", "origin")
	if !ok {
		logger.Fatalf("No origin configured for git.sr.ht")
	}

	repos, ok = config.Get("git.sr.ht", "repos")
	if !ok {
		logger.Fatalf("No repo path configured for git.sr.ht")
	}

	postUpdate, ok = config.Get("git.sr.ht", "post-update-script")
	if !ok {
		logger.Fatalf("No post-update script configured for git.sr.ht")
	}

	siteOwnerName, _ = config.Get("sr.ht", "owner-name")
	siteOwnerEmail, _ = config.Get("sr.ht", "owner-email")

	cmdstr, ok = os.LookupEnv("SSH_ORIGINAL_COMMAND")
	if !ok {
		cmdstr = ""
	}

	cmd, err = shlex.Split(cmdstr)
	if err != nil {
		logger.Fatalf("Unable to parse command: %v", err)
	}

	logger.Println("Running git.sr.ht shell")

	validCommands := []string{
		"git-receive-pack", "git-upload-pack", "git-upload-archive",
	}
	var valid bool
	for _, c := range validCommands {
		if len(cmd) > 0 && c == cmd[0] {
			valid = true
		}
	}

	if !valid {
		logger.Printf("Not permitting unacceptable command: %v", cmd)
		log.Printf("Hi %s! You've successfully authenticated, "+
			"but I do not provide an interactive shell. Bye!", pusherName)
		os.Exit(128)
	}

	os.Chdir(repos)

	path := cmd[len(cmd)-1]
	path, err = filepath.Abs(path)
	if err != nil {
		logger.Fatalf("filepath.Abs(%s): %v", path, err)
	}
	if !strings.HasPrefix(path, repos) {
		path = gopath.Join(repos, path)
	}
	cmd[len(cmd)-1] = path

	needsAccess := ACCESS_READ
	if cmd[0] == "git-receive-pack" {
		needsAccess = ACCESS_WRITE
	}

	pgcs, ok := config.Get("git.sr.ht", "connection-string")
	if !ok {
		logger.Fatalf("No connection string configured for git.sr.ht: %v", err)
	}
	db, err := sql.Open("postgres", pgcs)
	if err != nil {
		logger.Fatalf("Failed to open a database connection: %v", err)
	}

	// Note: when updating push access logic, also update scm.sr.ht/access.py
	var (
		repoId              int
		repoName            string
		repoOwnerId         int
		repoOwnerName       string
		repoVisibility      string
		pusherType          string
		pusherSuspendNotice string
		accessGrant         *string
	)
	row := db.QueryRow(`
		SELECT
			repo.id,
			repo.name,
			repo.owner_id,
			repo.visibility,
			owner.username,
			pusher.user_type,
			pusher.suspension_notice,
			access.mode
		FROM repository repo
		JOIN "user" owner  ON owner.id  = repo.owner_id
		JOIN "user" pusher ON pusher.id = $1
		LEFT JOIN access
			ON (access.repo_id = repo.id AND access.user_id = $1)
		WHERE
			repo.path = $2;
	`, pusherId, path)
	if err := row.Scan(&repoId, &repoName, &repoOwnerId, &repoOwnerName,
		&repoVisibility, &pusherType, &pusherSuspendNotice, &accessGrant); err != nil {

		row = db.QueryRow(`
			SELECT
				repo.id,
				repo.name,
				repo.owner_id,
				repo.visibility,
				owner.username,
				pusher.user_type,
				pusher.suspension_notice,
				access.mode
			FROM repository repo
			JOIN "user" owner  ON owner.id  = repo.owner_id
			JOIN "user" pusher ON pusher.id = $1
			JOIN redirect      ON redirect.new_repo_id = repo.id
			LEFT JOIN access
				ON (access.repo_id = repo.id AND access.user_id = $1)
			WHERE
				redirect.path = $2;
		`, pusherId, path)

		if err := row.Scan(&repoId, &repoName, &repoOwnerId, &repoOwnerName,
			&repoVisibility, &pusherType, &pusherSuspendNotice,
			&accessGrant); err != nil {

			repoName = gopath.Base(path)
			repoOwnerName = gopath.Base(gopath.Dir(path))
			if repoOwnerName != "" {
				repoOwnerName = repoOwnerName[1:]
			}

			notFound := func(ctx string, err error) {
				if err != nil {
					logger.Printf("Error autocreating repo: %s: %v", ctx, err)
				}
				log.Println("Repository not found.")
				log.Println()
				os.Exit(128)
			}

			if needsAccess == ACCESS_READ || repoOwnerName != pusherName {
				notFound("access", nil)
			}

			if needsAccess == ACCESS_WRITE {
				repoOwnerId = pusherId
				repoOwnerName = pusherName
				repoVisibility = "autocreated"

				createQuery, err := db.Prepare(`
					INSERT INTO repository (
						created,
						updated,
						name,
						owner_id,
						path,
						visibility
					) VALUES (
						NOW() at time zone 'utc',
						NOW() at time zone 'utc',
						$1, $2, $3, 'autocreated'
					) RETURNING id;
				`)
				if err != nil {
					notFound("create query prepare", err)
				}
				defer createQuery.Close()

				if createQuery.QueryRow(repoName, repoOwnerId, path).
					Scan(&repoId); err != nil {

					notFound("insert", err)
				}

				// Note: update gitsrht/repos.py when changing this
				if err = exec.Command("mkdir", "-p", path).Run(); err != nil {
					notFound("mkdir", err)
				}
				if err = exec.Command("git", "init",
					"--bare", path).Run(); err != nil {

					notFound("git init", err)
				}
				if err = exec.Command("ln", "-s", postUpdate,
					gopath.Join(path, "hooks", "update")).Run(); err != nil {

					notFound("ln update", err)
				}
				if err = exec.Command("ln", "-s", postUpdate,
					gopath.Join(path, "hooks", "post-update")).Run(); err != nil {

					notFound("ln post-update", err)
				}

				logger.Printf("Autocreated repo %s", path)
			}
		} else {
			log.Printf("\033[93mNOTICE\033[0m: This repository has moved.")
			log.Printf("Please update your remote to:")
			log.Println()
			log.Printf("\t%s/~%s/%s", origin, repoOwnerName, repoName)
			log.Println()
		}
	}

	hasAccess := ACCESS_NONE
	if pusherId == repoOwnerId {
		hasAccess = ACCESS_READ | ACCESS_WRITE | ACCESS_MANAGE
	} else {
		if accessGrant == nil {
			switch repoVisibility {
			case "public":
				fallthrough
			case "unlisted":
				hasAccess = ACCESS_READ
			case "private":
				hasAccess = ACCESS_NONE
			default:
				hasAccess = ACCESS_NONE
			}
		} else {
			switch *accessGrant {
			case "r":
				hasAccess = ACCESS_READ
			case "rw":
				hasAccess = ACCESS_WRITE
			default:
				hasAccess = ACCESS_NONE
			}
		}
	}

	if needsAccess&hasAccess != needsAccess {
		log.Println("Access denied.")
		log.Println()
		os.Exit(128)
	}

	if pusherType == "suspended" {
		log.Println("Your account has been suspended for the following reason:")
		log.Println()
		log.Println("\t" + pusherSuspendNotice)
		log.Println()
		log.Printf("Please contact support: %s <%s>",
			siteOwnerName, siteOwnerEmail)
		log.Println()
		os.Exit(128)
	}

	type RepoContext struct {
		Id         int    `json:"id"`
		Name       string `json:"name"`
		Path       string `json:"path"`
		Visibility string `json:"visibility"`
	}

	type UserContext struct {
		CanonicalName string `json:"canonical_name"`
		Name          string `json:"name"`
	}

	pushContext, _ := json.Marshal(struct {
		Repo RepoContext `json:"repo"`
		User UserContext `json:"user"`
	}{
		Repo: RepoContext{
			Id:         repoId,
			Name:       repoName,
			Path:       path,
			Visibility: repoVisibility,
		},
		User: UserContext{
			CanonicalName: "~" + pusherName,
			Name:          pusherName,
		},
	})

	logger.Printf("Executing command: %v", cmd)
	bin, err := exec.LookPath(cmd[0])
	if err != nil {
		logger.Fatalf("exec.LookPath: %v", err)
	}
	if err := syscall.Exec(bin, cmd,
		append(os.Environ(), fmt.Sprintf(
			"SRHT_PUSH_CTX=%s", string(pushContext)))); err != nil {

		logger.Fatalf("syscall.Exec: %v", err)
	}
}
