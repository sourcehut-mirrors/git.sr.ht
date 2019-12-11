package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"syscall"

	goredis "github.com/go-redis/redis"
	_ "github.com/lib/pq"
	"gopkg.in/src-d/go-git.v4"
	"gopkg.in/src-d/go-git.v4/plumbing"
	"gopkg.in/src-d/go-git.v4/plumbing/object"
)

func printAutocreateInfo(context PushContext) {
	log.Println("\n\t\033[93mNOTICE\033[0m")
	log.Println("\tWe saved your changes, but this repository does not exist.")
	log.Println("\tClick here to create it:")
	log.Println()
	log.Printf("\t%s/create?name=%s", origin, context.Repo.Name)
	log.Println()
	log.Println("\tYour changes will be discarded in 20 minutes.")
	log.Println()
}

type DbInfo struct {
	RepoId        int
	RepoName      string
	Visibility    string
	OwnerUsername string
	OwnerToken    *string
	AsyncWebhooks []WebhookSubscription
	SyncWebhooks  []WebhookSubscription
}

func fetchInfoForPush(db *sql.DB, repoId int) (DbInfo, error) {
	var dbinfo DbInfo = DbInfo{RepoId: repoId}

	// With this query, we:
	// 1. Fetch the owner's username and OAuth token
	// 2. Fetch the repository's name and visibility
	// 3. Update the repository's mtime
	// 4. Determine how many webhooks this repo has: if there are zero sync
	//    webhooks then we can defer looking them up until after we've sent the
	//    user on their way.
	query, err := db.Prepare(`
		UPDATE repository repo
		SET updated = NOW() AT TIME ZONE 'UTC'
		FROM (
			SELECT "user".username, "user".oauth_token
			FROM "user"
			JOIN repository r ON r.owner_id = "user".id
			WHERE r.id = $1
		) AS owner, (
			SELECT
				COUNT(*) FILTER(WHERE rws.sync = true) sync_count,
				COUNT(*) FILTER(WHERE rws.sync = false) async_count
			FROM repo_webhook_subscription rws
			WHERE rws.repo_id = $1 AND rws.events LIKE '%repo:post-update%'
		) AS webhooks
		WHERE repo.id = $1
		RETURNING
			repo.name,
			repo.visibility,
			owner.username,
			owner.oauth_token,
			webhooks.sync_count,
			webhooks.async_count;
	`)
	if err != nil {
		return dbinfo, err
	}
	defer query.Close()

	var nasync, nsync int
	if err = query.QueryRow(repoId).Scan(&dbinfo.RepoName, &dbinfo.Visibility,
		&dbinfo.OwnerUsername, &dbinfo.OwnerToken,
		&nsync, &nasync); err != nil {

		return dbinfo, err
	}

	dbinfo.AsyncWebhooks = make([]WebhookSubscription, nasync)
	dbinfo.SyncWebhooks = make([]WebhookSubscription, nsync)
	if nsync == 0 {
		// Don't fetch webhooks, we don't need to waste the user's time
		return dbinfo, nil
	}

	var rows *sql.Rows
	if rows, err = db.Query(`
			SELECT id, url, events
			FROM repo_webhook_subscription rws
			WHERE rws.repo_id = $1
				AND rws.events LIKE '%repo:post-update%'
				AND rws.sync = true
		`, repoId); err != nil {

		return dbinfo, err
	}
	defer rows.Close()

	for i := 0; rows.Next(); i++ {
		var whs WebhookSubscription
		if err = rows.Scan(&whs.Id, &whs.Url, &whs.Events); err != nil {
			return dbinfo, err
		}
		dbinfo.SyncWebhooks[i] = whs
	}

	return dbinfo, nil
}

func postUpdate() {
	var context PushContext
	refs := os.Args[1:]

	contextJson, ctxOk := os.LookupEnv("SRHT_PUSH_CTX")
	pushUuid, pushOk := os.LookupEnv("SRHT_PUSH")
	if !ctxOk || !pushOk {
		logger.Fatal("Missing required variables in environment, " +
			"configuration error?")
	}

	logger.Printf("Running post-update for push %s", pushUuid)

	if err := json.Unmarshal([]byte(contextJson), &context); err != nil {
		logger.Fatalf("unmarshal SRHT_PUSH_CTX: %v", err)
	}

	if context.Repo.Visibility == "autocreated" {
		printAutocreateInfo(context)
	}

	initSubmitter()

	payload := WebhookPayload{
		Push:   pushUuid,
		Pusher: context.User,
		Refs:   make([]UpdatedRef, len(refs)),
	}

	oids := make(map[string]interface{})
	repo, err := git.PlainOpen(context.Repo.Path)
	if err != nil {
		logger.Fatalf("git.PlainOpen: %v", err)
	}

	db, err := sql.Open("postgres", pgcs)
	if err != nil {
		logger.Fatalf("Failed to open a database connection: %v", err)
	}

	dbinfo, err := fetchInfoForPush(db, context.Repo.Id)
	if err != nil {
		logger.Fatalf("Failed to fetch info from database: %v", err)
	}

	redisHost, ok := config.Get("sr.ht", "redis-host")
	if !ok {
		redisHost = "localhost"
	}
	redisHost += ":6379"
	redis := goredis.NewClient(&goredis.Options{Addr: redisHost})
	for i, refname := range refs {
		var oldref, newref string
		var oldobj, newobj object.Object
		updateKey := fmt.Sprintf("update.%s.%s", pushUuid, refname)
		update, err := redis.Get(updateKey).Result()
		if update == "" || err != nil {
			logger.Println("redis.Get: missing key")
			continue
		} else {
			parts := strings.Split(update, ":")
			oldref = parts[0]
			newref = parts[1]
		}
		oldobj, err = repo.Object(plumbing.AnyObject, plumbing.NewHash(oldref))
		if err == plumbing.ErrObjectNotFound {
			oldobj = nil
		}
		newobj, err = repo.Object(plumbing.AnyObject, plumbing.NewHash(newref))
		if err == plumbing.ErrObjectNotFound {
			logger.Printf("new object %s not found", newref)
			continue
		}

		var atag *AnnotatedTag = nil
		if tag, ok := newobj.(*object.Tag); ok {
			atag = &AnnotatedTag{
				Name:    tag.Name,
				Message: tag.Message,
			}
			newobj, err = repo.CommitObject(tag.Target)
			if err != nil {
				logger.Println("unresolvable annotated tag")
				continue
			}
		}

		commit, ok := newobj.(*object.Commit)
		if !ok {
			logger.Println("Skipping non-commit new ref")
			continue
		}

		payload.Refs[i] = UpdatedRef{
			Tag:  atag,
			Name: refname,
			New:  GitCommitToWebhookCommit(commit),
		}

		if oldobj != nil {
			oldcommit, ok := oldobj.(*object.Commit)
			if !ok {
				logger.Println("Skipping non-commit old ref")
			} else {
				payload.Refs[i].Old = GitCommitToWebhookCommit(oldcommit)
			}
		}

		if _, ok := oids[commit.Hash.String()]; ok {
			continue
		}
		oids[commit.Hash.String()] = nil

		if buildOrigin != "" {
			submitter := GitBuildSubmitter{
				BuildOrigin: buildOrigin,
				Commit:      commit,
				GitOrigin:   origin,
				OwnerName:   dbinfo.OwnerUsername,
				OwnerToken:  dbinfo.OwnerToken,
				RepoName:    dbinfo.RepoName,
				Repository:  repo,
				Visibility:  dbinfo.Visibility,
			}
			results, err := SubmitBuild(submitter)
			if err != nil {
				log.Fatalf("Error submitting build job: %v", err)
			}
			if len(results) == 0 {
				continue
			} else if len(results) == 1 {
				log.Println("\033[1mBuild started:\033[0m")
			} else {
				log.Println("\033[1mBuilds started:\033[0m")
			}
			logger.Printf("Submitted %d builds for %s",
				len(results), refname)
			for _, result := range results {
				log.Printf("\033[94m%s\033[0m [%s]", result.Url, result.Name)
			}
		}
	}

	payloadBytes, err := json.Marshal(&payload)
	if err != nil {
		logger.Fatalf("Failed to marshal webhook payload: %v", err)
	}

	deliveries := deliverWebhooks(dbinfo.SyncWebhooks, payloadBytes, true)
	deliveriesJson, err := json.Marshal(deliveries)
	if err != nil {
		logger.Fatalf("Failed to marshal webhook deliveries: %v", err)
	}

	hook, ok := config.Get("git.sr.ht", "post-update-script")
	if !ok {
		logger.Fatal("No post-update script configured, cannot run stage 3")
	}

	if len(deliveries) == 0 && len(dbinfo.AsyncWebhooks) == 0 {
		logger.Println("Skipping stage 3, no work")
		return
	}

	// Run stage 3 asyncronously - the last few tasks can be done without
	// blocking the pusher's terminal.
	wd, err := os.Getwd()
	if err != nil {
		log.Fatalf("Failed to execute stage 3: %v", err)
	}

	procAttr := syscall.ProcAttr{
		Dir:   wd,
		Files: []uintptr{os.Stdin.Fd(), os.Stdout.Fd(), os.Stderr.Fd()},
		Env:   os.Environ(),
		Sys: &syscall.SysProcAttr{
			Foreground: false,
		},
	}
	pid, err := syscall.ForkExec(hook, []string{
		"hooks/stage-3", string(deliveriesJson), string(payloadBytes),
	}, &procAttr)
	if err != nil {
		log.Fatalf("Failed to execute stage 3: %v", err)
	}

	logger.Printf("Executing stage 3 to record %d sync deliveries and make "+
		"%d async deliveries (pid %d)", len(deliveries),
		len(dbinfo.AsyncWebhooks), pid)
}
