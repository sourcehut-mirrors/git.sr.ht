package webhooks

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"time"

	"git.sr.ht/~sircmpwn/core-go/auth"
	"git.sr.ht/~sircmpwn/core-go/webhooks"
	sq "github.com/Masterminds/squirrel"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/model"
)

func NewLegacyQueue() *webhooks.LegacyQueue {
	return webhooks.NewLegacyQueue()
}

var legacyUserCtxKey = &contextKey{"legacyUser"}

type contextKey struct {
	name string
}

func LegacyMiddleware(
	queue *webhooks.LegacyQueue) func(next http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := context.WithValue(r.Context(), legacyUserCtxKey, queue)
			r = r.WithContext(ctx)
			next.ServeHTTP(w, r)
		})
	}
}

func DeliverLegacyRepoCreate(ctx context.Context, repo *model.Repository) {
	q, ok := ctx.Value(legacyUserCtxKey).(*webhooks.LegacyQueue)
	if !ok {
		panic(errors.New("No legacy user webhooks worker for this context"))
	}

	type WebhookPayload struct {
		ID          int       `json:"id"`
		Created     time.Time `json:"created"`
		Updated     time.Time `json:"updated"`
		Name        string    `json:"name"`
		Description *string   `json:"description"`
		Visibility  string    `json:"visibility"`

		Owner struct {
			CanonicalName string  `json:"canonical_name"`
			Name          string  `json:"name"`
		}`json:"owner"`
	}

	payload := WebhookPayload{
		ID:          repo.ID,
		Created:     repo.Created,
		Updated:     repo.Created,
		Name:        repo.Name,
		Description: repo.Description,
		Visibility:  repo.RawVisibility,
	}

	// TODO: User groups
	user := auth.ForContext(ctx)
	if user.UserID != repo.OwnerID {
		// At the time of writing, the only consumers of this function are in a
		// context where the authenticated user is the owner of this repo. We
		// can skip the database round-trip if we just grab their auth context.
		panic(errors.New("TODO: look up user details for this repo"))
	}
	payload.Owner.CanonicalName = "~" + user.Username
	payload.Owner.Name = user.Username

	encoded, err := json.Marshal(&payload)
	if err != nil {
		panic(err) // Programmer error
	}

	query := sq.
		Select().
		From("user_webhook_subscription sub").
		Where("sub.user_id = ?", repo.OwnerID)
	q.Schedule(query, "user", "repo:create", encoded)
}
