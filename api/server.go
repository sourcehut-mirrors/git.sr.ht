package main

import (
	"context"
	"database/sql"
	"fmt"
	"io"
	"net/http"
	"path"

	"git.sr.ht/~sircmpwn/core-go/config"
	"git.sr.ht/~sircmpwn/core-go/database"
	"git.sr.ht/~sircmpwn/core-go/objects"
	"git.sr.ht/~sircmpwn/core-go/server"
	"git.sr.ht/~sircmpwn/core-go/webhooks"
	work "git.sr.ht/~sircmpwn/dowork"
	"github.com/99designs/gqlgen/graphql"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/go-chi/chi/v5"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/account"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/api"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/model"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/loaders"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/repos"
)

func main() {
	appConfig := config.LoadConfig(":5101")

	gqlConfig := api.Config{Resolvers: &graph.Resolver{}}
	gqlConfig.Directives.Private = server.Private
	gqlConfig.Directives.Anoninternal = server.AnonInternal
	gqlConfig.Directives.Internal = server.Internal
	gqlConfig.Directives.Access = func(ctx context.Context, obj interface{},
		next graphql.Resolver, scope model.AccessScope,
		kind model.AccessKind) (interface{}, error) {
		return server.Access(ctx, obj, next, scope.String(), kind.String())
	}
	schema := api.NewExecutableSchema(gqlConfig)

	scopes := make([]string, len(model.AllAccessScope))
	for i, s := range model.AllAccessScope {
		scopes[i] = s.String()
	}

	queueSize := config.GetInt(appConfig, "git.sr.ht::api",
		"repo-worker-queue-size", config.DefaultQueueSize)
	reposQueue := work.NewQueue("repos", queueSize)
	queueSize = config.GetInt(appConfig, "git.sr.ht::api",
		"account-del-queue-size", config.DefaultQueueSize)
	accountQueue := work.NewQueue("account", queueSize)
	webhookQueue := webhooks.NewQueue(schema, appConfig)
	legacyWebhooks := webhooks.NewLegacyQueue(appConfig)

	srv := server.NewServer("git.sr.ht", appConfig).
		WithDefaultMiddleware().
		WithMiddleware(
			loaders.Middleware,
			account.Middleware(accountQueue),
			repos.Middleware(reposQueue),
			webhooks.Middleware(webhookQueue),
			webhooks.LegacyMiddleware(legacyWebhooks),
		).
		WithSchema(schema, scopes).
		WithQueues(
			accountQueue,
			reposQueue,
			webhookQueue.Queue,
			legacyWebhooks.Queue)

	srv.Router().HandleFunc("/query/artifact/{checksum}/{filename}", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			w.WriteHeader(http.StatusMethodNotAllowed)
			w.Write([]byte("Method not allowed\r\n"))
			return
		}

		ctx := r.Context()
		checksum := chi.URLParam(r, "checksum")
		filename := chi.URLParam(r, "filename")

		var (
			repoName  string
			ownerName string
		)
		if err := database.WithTx(ctx, &sql.TxOptions{
			ReadOnly:  true,
			Isolation: 0,
		}, func(tx *sql.Tx) error {
			row := tx.QueryRowContext(ctx, `
			SELECT
				repo.name,
				"user".username
			FROM artifacts
			JOIN repository repo ON repo.id = repo_id
			JOIN "user" on "user".id = repo.owner_id
			WHERE checksum = $1 AND filename = $2
			`, checksum, filename)
			return row.Scan(&repoName, &ownerName)
		}); err != nil {
			if err == sql.ErrNoRows {
				w.WriteHeader(http.StatusNotFound)
				w.Write([]byte("Not found\n"))
			} else {
				w.WriteHeader(http.StatusInternalServerError)
				w.Write([]byte(err.Error()))
			}
			return
		}

		sc, err := objects.NewClient(appConfig)
		if err != nil {
			panic(err)
		}

		bucket, _ := appConfig.Get("git.sr.ht", "s3-bucket")
		prefix, _ := appConfig.Get("git.sr.ht", "s3-prefix")

		s3key := path.Join(prefix, "artifacts",
			"~"+ownerName, repoName, filename)
		obj, err := sc.GetObject(r.Context(), &s3.GetObjectInput{
			Bucket: aws.String(bucket),
			Key:    aws.String(s3key),
		})
		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(err.Error()))
			return
		}
		defer obj.Body.Close()

		w.Header().Add("Content-Type", "application/octet-stream")
		w.Header().Set("Content-Length",
			fmt.Sprintf("%d", *obj.ContentLength))

		if r.Method == http.MethodGet {
			io.Copy(w, obj.Body)
		}
	})

	srv.Run()
}
