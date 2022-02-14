package clones

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

type ClonesQueue struct {
	Queue *work.Queue
}

func NewQueue() *ClonesQueue {
	return &ClonesQueue{work.NewQueue("clones")}
}

type contextKey struct {
	name string
}

var clonesCtxKey = &contextKey{"clones"}

func Middleware(queue *ClonesQueue) func(next http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := context.WithValue(r.Context(), clonesCtxKey, queue)
			r = r.WithContext(ctx)
			next.ServeHTTP(w, r)
		})
	}
}

// Schedules a clone.
func Schedule(ctx context.Context, repoID int, repo *git.Repository, cloneURL string) {
	queue, ok := ctx.Value(clonesCtxKey).(*ClonesQueue)
	if !ok {
		panic("No clones worker for this context")
	}
	task := work.NewTask(func(ctx context.Context) error {
		defer func() {
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
	queue.Queue.Enqueue(task)
	log.Printf("Enqueued clone of %s", cloneURL)
}
