package repos

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"path"
	"time"

	"git.sr.ht/~sircmpwn/core-go/config"
	"git.sr.ht/~sircmpwn/core-go/database"
	work "git.sr.ht/~sircmpwn/dowork"
	"github.com/go-git/go-git/v5"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

type contextKey struct {
	name string
}

var ctxKey = &contextKey{"repos"}

func Middleware(queue *work.Queue) func(next http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := context.WithValue(r.Context(), ctxKey, queue)
			r = r.WithContext(ctx)
			next.ServeHTTP(w, r)
		})
	}
}

type CloneStatus string

const (
	CloneNone       CloneStatus = "NONE"
	CloneInProgress CloneStatus = "IN_PROGRESS"
	CloneComplete   CloneStatus = "COMPLETE"
	CloneError      CloneStatus = "ERROR"
)

// Schedules a clone.
func Clone(ctx context.Context, repoID int, repo *git.Repository, cloneURL string) {
	queue, ok := ctx.Value(ctxKey).(*work.Queue)
	if !ok {
		panic("No repos worker for this context")
	}
	task := work.NewTask(func(ctx context.Context) error {
		cloneCtx, cancel := context.WithTimeout(ctx, 10*time.Minute)
		defer cancel()
		err := repo.Clone(cloneCtx, &git.CloneOptions{
			URL:               cloneURL,
			RecurseSubmodules: git.NoRecurseSubmodules,
		})
		cloneStatus := CloneComplete
		var cloneError sql.NullString
		if err != nil {
			cloneStatus = CloneError
			cloneError.String = err.Error()
			cloneError.Valid = true
		}
		if err := database.WithTx(ctx, nil, func(tx *sql.Tx) error {
			_, err := tx.Exec(`
				UPDATE repository
				SET clone_status = $2, clone_error = $3
				WHERE id = $1;`, repoID, cloneStatus, cloneError)
			if err != nil {
				return err
			}
			return nil
		}); err != nil {
			panic(err)
		}
		return nil
	})
	queue.Enqueue(task)
	log.Printf("Enqueued clone of %s", cloneURL)
}

// Schedules deletion of artifacts.
func DeleteArtifacts(ctx context.Context, username, repoName string, filenames []string) {
	queue, ok := ctx.Value(ctxKey).(*work.Queue)
	if !ok {
		panic("No repos worker for this context")
	}
	task := work.NewTask(func(ctx context.Context) error {
		conf := config.ForContext(ctx)
		upstream, _ := conf.Get("objects", "s3-upstream")
		accessKey, _ := conf.Get("objects", "s3-access-key")
		secretKey, _ := conf.Get("objects", "s3-secret-key")
		bucket, _ := conf.Get("git.sr.ht", "s3-bucket")
		prefix, _ := conf.Get("git.sr.ht", "s3-prefix")

		if upstream == "" || accessKey == "" || secretKey == "" || bucket == "" {
			return fmt.Errorf("Object storage is not enabled for this server")
		}

		mc, err := minio.New(upstream, &minio.Options{
			Creds:  credentials.NewStaticV4(accessKey, secretKey, ""),
			Secure: true,
		})
		if err != nil {
			panic(err)
		}

		for _, filename := range filenames {
			s3path := path.Join(prefix, "artifacts", "~"+username, repoName, filename)
			if err := mc.RemoveObject(ctx, bucket, s3path, minio.RemoveObjectOptions{}); err != nil {
				return err
			}
		}
		return nil
	})
	queue.Enqueue(task)
	log.Printf("Enqueued deletion of %d artifacts", len(filenames))
}
