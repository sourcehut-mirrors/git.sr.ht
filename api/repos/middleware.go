package repos

import (
	"context"
	"database/sql"
	"log"
	"net/http"
	"time"

	"git.sr.ht/~sircmpwn/core-go/database"
	work "git.sr.ht/~sircmpwn/dowork"
	"github.com/go-git/go-git/v5"
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

// Schedules a clone.
func Clone(ctx context.Context, repoID int, repo *git.Repository, cloneURL string) {
	queue, ok := ctx.Value(ctxKey).(*work.Queue)
	if !ok {
		panic("No repos worker for this context")
	}
	task := work.NewTask(func(ctx context.Context) error {
		defer func() {
			recovered := recover()
			err := database.WithTx(ctx, nil, func(tx *sql.Tx) error {
				_, err := tx.Exec(
					`UPDATE repository SET clone_in_progress = false WHERE id = $1;`,
					repoID,
				)
				if err != nil {
					return err
				}
				return nil
			})
			if err != nil {
				panic(err)
			}
			if recovered != nil {
				panic(recovered)
			}
		}()
		cloneCtx, cancel := context.WithTimeout(ctx, 10*time.Minute)
		defer cancel()
		err := repo.Clone(cloneCtx, &git.CloneOptions{
			URL:               cloneURL,
			RecurseSubmodules: git.NoRecurseSubmodules,
		})
		if err != nil {
			// TODO: Set repo to error state. Email error to user.
			panic(err)
		}
		return nil
	})
	queue.Enqueue(task)
	log.Printf("Enqueued clone of %s", cloneURL)
}
