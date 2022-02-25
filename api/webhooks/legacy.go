package webhooks

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"time"

	"git.sr.ht/~sircmpwn/core-go/auth"
	"git.sr.ht/~sircmpwn/core-go/webhooks"
	sq "github.com/Masterminds/squirrel"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/model"
)

type RepoWebhookPayload struct {
	ID          int       `json:"id"`
	Created     time.Time `json:"created"`
	Updated     time.Time `json:"updated"`
	Name        string    `json:"name"`
	Description *string   `json:"description"`
	Visibility  string    `json:"visibility"`

	Owner struct {
		CanonicalName string `json:"canonical_name"`
		Name          string `json:"name"`
	} `json:"owner"`
}

func DeliverLegacyRepoCreate(ctx context.Context, repo *model.Repository) {
	q := webhooks.LegacyForContext(ctx)
	payload := RepoWebhookPayload{
		ID:          repo.ID,
		Created:     repo.Created,
		Updated:     repo.Created,
		Name:        repo.Name,
		Description: repo.Description,
		Visibility:  strings.ToLower(repo.Visibility.String()),
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
	q.Schedule(ctx, query, "user", "repo:create", encoded)
}

func DeliverLegacyRepoUpdate(ctx context.Context, repo *model.Repository) {
	q := webhooks.LegacyForContext(ctx)
	payload := RepoWebhookPayload{
		ID:          repo.ID,
		Created:     repo.Created,
		Updated:     repo.Created,
		Name:        repo.Name,
		Description: repo.Description,
		Visibility:  strings.ToLower(repo.Visibility.String()),
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
	q.Schedule(ctx, query, "user", "repo:update", encoded)
}

func DeliverLegacyRepoDeleted(ctx context.Context, repo *model.Repository) {
	q := webhooks.LegacyForContext(ctx)
	payload := struct {
		ID int `json:"id"`
	}{repo.ID}

	encoded, err := json.Marshal(&payload)
	if err != nil {
		panic(err) // Programmer error
	}

	query := sq.
		Select().
		From("user_webhook_subscription sub").
		Where("sub.user_id = ?", repo.OwnerID)
	q.Schedule(ctx, query, "user", "repo:delete", encoded)
}
