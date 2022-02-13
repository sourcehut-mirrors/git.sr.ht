package main

import (
	"context"
	ctx "context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"syscall"
	"time"

	"git.sr.ht/~sircmpwn/core-go/client"
	coreconfig "git.sr.ht/~sircmpwn/core-go/config"
	"github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/plumbing"
	"github.com/go-git/go-git/v5/plumbing/object"
	"github.com/go-git/go-git/v5/plumbing/storer"
	goredis "github.com/go-redis/redis/v8"
	_ "github.com/lib/pq"
	"github.com/vektah/gqlparser/gqlerror"
)

func printAutocreateInfo(context PushContext) {
	log.Println("\n\t\033[93mNOTICE\033[0m")
	log.Printf(`
	You have pushed to a repository which did not exist. %[2]s/%[3]s
	has been created automatically. You can re-configure or delete this
	repository at the following URL:

	%[1]s/%[2]s/%[3]s/settings/info

`, origin, context.User.CanonicalName, context.Repo.Name)
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

func fetchInfoForPush(db *sql.DB, username string, repoId int, repoName string,
	repoVisibility string, newDescription *string, newVisibility *string) (DbInfo, error) {
	var dbinfo DbInfo = DbInfo{
		RepoId:     repoId,
		RepoName:   repoName,
		Visibility: repoVisibility,
	}

	type RepoInput struct {
		Description *string `json:"description,omitempty"`
		Visibility  *string `json:"visibility,omitempty"`
	}

	type Response struct {
		Errors []gqlerror.Error `json:"errors"`
	}

	if newDescription != nil || newVisibility != nil {
		input := RepoInput{newDescription, newVisibility}
		resp := Response{}

		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		ctx = coreconfig.Context(ctx, config, "git.sr.ht")
		err := client.Execute(ctx, username, "git.sr.ht", client.GraphQLQuery{
			Query: `
			mutation UpdateRepository($id: Int!, $input: RepoInput!) {
				updateRepository(id: $id, input: $input) { id }
			}`,
			Variables: map[string]interface{}{
				"id":    repoId,
				"input": input,
			},
		}, &resp)
		if err != nil {
			return dbinfo, err
		} else if len(resp.Errors) > 0 {
			for _, err := range resp.Errors {
				logger.Printf("Error updating repository: %s", err.Error())
			}
			return dbinfo, fmt.Errorf("Failed to update repository: %s", resp.Errors[0].Message)
		}

		if newVisibility != nil {
			dbinfo.Visibility = *newVisibility
		}
	}

	// With this query, we:
	// 1. Fetch the owner's username and OAuth token
	// 2. Determine how many webhooks this repo has: if there are zero sync
	//    webhooks then we can defer looking them up until after we've sent the
	//    user on their way.

	query, err := db.Prepare(`
		WITH owner AS (
			SELECT "user".username, "user".oauth_token
			FROM "user"
			JOIN repository r ON r.owner_id = "user".id
			WHERE r.id = $1
		), webhooks AS (
			SELECT
				COUNT(*) FILTER(WHERE rws.sync = true) sync_count,
				COUNT(*) FILTER(WHERE rws.sync = false) async_count
			FROM repo_webhook_subscription rws
			WHERE rws.repo_id = $1 AND rws.events LIKE '%repo:post-update%'
		)
		SELECT
			owner.username,
			owner.oauth_token,
			webhooks.sync_count,
			webhooks.async_count
		FROM owner, webhooks;
	`)
	if err != nil {
		return dbinfo, err
	}
	defer query.Close()

	var nasync, nsync int
	if err = query.QueryRow(repoId).Scan(&dbinfo.OwnerUsername,
		&dbinfo.OwnerToken, &nsync, &nasync); err != nil {

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

func parseUpdatables() (*string, *string) {
	loadOptions()
	var desc, vis *string

	if newDescription, ok := options["description"]; ok {
		desc = &newDescription
	}
	if newVisibility, ok := options["visibility"]; ok {
		newVisibility = strings.ToUpper(newVisibility)
		vis = &newVisibility
	}
	return desc, vis
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

	initSubmitter()

	newDescription, newVisibility := parseUpdatables()
	if context.Repo.Autocreated && newVisibility == nil {
		printAutocreateInfo(context)
	}

	loadOptions()
	payload := WebhookPayload{
		Push:     pushUuid,
		PushOpts: options,
		Pusher:   context.User,
		Refs:     make([]UpdatedRef, len(refs)),
	}

	oids := make(map[string]interface{})
	repo, err := git.PlainOpen(context.Repo.AbsolutePath)
	if err != nil {
		logger.Fatalf("git.PlainOpen(%q): %v", context.Repo.AbsolutePath, err)
	}

	db, err := sql.Open("postgres", pgcs)
	if err != nil {
		logger.Fatalf("Failed to open a database connection: %v", err)
	}

	dbinfo, err := fetchInfoForPush(db, context.User.Name, context.Repo.Id, context.Repo.Name, context.Repo.Visibility, newDescription, newVisibility)
	if err != nil {
		logger.Fatalf("Failed to fetch info from database: %v", err)
	}

	refsDeleted := false
	redisHost, ok := config.Get("sr.ht", "redis-host")
	if !ok {
		redisHost = "redis://localhost:6379"
	}
	ropts, err := goredis.ParseURL(redisHost)
	if err != nil {
		logger.Fatalf("Failed to parse redis host: %v", err)
	}
	nbuilds := 0
	redis := goredis.NewClient(ropts)
	for i, refname := range refs {
		var oldref, newref string
		var oldobj, newobj object.Object
		updateKey := fmt.Sprintf("update.%s.%s", pushUuid, refname)
		update, err := redis.Get(ctx.Background(), updateKey).Result()
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
		} else if tag, ok := oldobj.(*object.Tag); ok {
			oldobj, err = repo.CommitObject(tag.Target)
			if err != nil {
				logger.Printf("old tag cannot be resolved: %v", err)
				continue
			}
		}

		newobj, err = repo.Object(plumbing.AnyObject, plumbing.NewHash(newref))
		if err == plumbing.ErrObjectNotFound {
			payload.Refs[i] = UpdatedRef{
				Name: refname,
				New:  nil,
			}
			if oldcommit, ok := oldobj.(*object.Commit); ok {
				payload.Refs[i].Old = GitCommitToWebhookCommit(oldcommit)
			}
			refsDeleted = true
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
				logger.Printf("new tag cannot be resovled: %v", err)
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

		if buildOrigin != "" && nbuilds < 4 {
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
				logger.Printf("Error submitting build job: %v", err)
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
				if _, ok := options["debug"]; ok {
					log.Printf("[debug] builds.sr.ht response: \n%s", result.Response)
				}
				log.Printf("\033[94m%s\033[0m [%s]", result.Url, result.Name)
			}
			nbuilds += len(results)
		}
	}

	// Check if HEAD's dangling (i.e. the default branch doesn't exist)
	// if so, try to find a branch from this push to set as the default
	// if none were found, set the first branch in iteration order as default
	head, err := repo.Reference("HEAD", false)
	if err != nil {
		logger.Fatalf("repo.Reference(\"HEAD\"): %v", err)
	}

	danglingHead := false
	if _, err = repo.Reference(head.Target(), false); err != nil {
		danglingHead = true
	}

	if danglingHead {
		logger.Printf("HEAD dangling at %s", head.Target())

		cbk := func(ref *plumbing.Reference) error {
			if ref == nil {
				return nil
			}

			logger.Printf("Setting HEAD to %s", ref.Name())
			log.Printf("Default branch updated to %s", ref.Name()[len("refs/heads/"):])
			repo.Storer.SetReference(plumbing.NewSymbolicReference("HEAD", ref.Name()))
			danglingHead = false
			return storer.ErrStop
		}
		for _, refName := range refs {
			if !strings.HasPrefix(refName, "refs/heads/") {
				continue
			}

			ref, _ := repo.Reference(plumbing.ReferenceName(refName), false)
			if cbk(ref) != nil {
				break
			}
		}

		if danglingHead {
			if branches, _ := repo.Branches(); branches != nil {
				branches.ForEach(cbk)
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

	if len(deliveries) == 0 && len(dbinfo.AsyncWebhooks) == 0 && !refsDeleted {
		logger.Println("Skipping stage 3, no work")
		return
	}

	// Run stage 3 asynchronously - the last few tasks can be done without
	// blocking the pusher's terminal.
	var stage3Pipe [2]int
	if err := syscall.Pipe(stage3Pipe[:]); err != nil {
		log.Fatalf("Failed to execute stage 3: %v", err)
	}
	syscall.CloseOnExec(stage3Pipe[1])

	procAttr := syscall.ProcAttr{
		Dir:   "",
		Files: []uintptr{uintptr(stage3Pipe[0]), os.Stdout.Fd(), os.Stderr.Fd()},
		Env:   os.Environ(),
		Sys: &syscall.SysProcAttr{
			Foreground: false,
		},
	}
	pid, err := syscall.ForkExec(hook, []string{
		"hooks/stage-3",
		strconv.Itoa(len(deliveriesJson)), strconv.Itoa(len(payloadBytes)),
	}, &procAttr)
	if err != nil {
		log.Fatalf("Failed to execute stage 3: %v", err)
	}

	stage3File := os.NewFile(uintptr(stage3Pipe[1]), "stage3 IPC")
	if _, err = stage3File.Write(deliveriesJson); err != nil {
		log.Fatalf("Failed to execute stage 3: %v", err)
	}
	if _, err = stage3File.Write(payloadBytes); err != nil {
		log.Fatalf("Failed to execute stage 3: %v", err)
	}

	logger.Printf("Executing stage 3 to record %d sync deliveries and make "+
		"%d async deliveries (pid %d)", len(deliveries),
		len(dbinfo.AsyncWebhooks), pid)
}
