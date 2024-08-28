package model

import (
	"context"
	"time"

	"github.com/go-git/go-git/v5/plumbing"
)

// This event is used for pre-receive and post-receive git hooks.
//
// If a pre-receive event is configured to be delievered synchronously, the git
// push operation is blocked until the webhook destination server returns a
// response. If the response code is not 200 OK, the push operation is cancelled.
// This allows the webhook user to accept or reject pushes according to
// user-specific policy, for instance enforcing an OWNERS file or denying certain
// users the right to push to certain branches. If a push is rejected, the HTTP
// response content is printed on the pushing user's console.
//
// post-receive events are never processed synchronously and the HTTP response has
// no outcome on the push operation.
type GitEvent struct {
	UUID       string        `json:"uuid"`
	Event      WebhookEvent  `json:"event"`
	Date       time.Time     `json:"date"`
	Repository *Repository   `json:"repository"`
	Pusher     Entity        `json:"pusher"`
	Updates    []*UpdatedRef `json:"updates"`
}

func (GitEvent) IsWebhookPayload() {}

type UpdatedRef struct {
	repo    *Repository
	ref     *plumbing.Reference
	oldHash *plumbing.Hash
	newHash *plumbing.Hash
}

func NewUpdatedRef(
	repo *Repository,
	ref *plumbing.Reference,
	oldHash, newHash *plumbing.Hash) UpdatedRef {
	return UpdatedRef{repo, ref, oldHash, newHash}
}

func (ref *UpdatedRef) Ref() (*Reference, error) {
	return &Reference{ref.repo, ref.ref}, nil
}

func (ref *UpdatedRef) Old() (Object, error) {
	return LookupObject(ref.repo.Repo(), *ref.oldHash)
}

func (ref *UpdatedRef) New() (Object, error) {
	return LookupObject(ref.repo.Repo(), *ref.newHash)
}

func (ref *UpdatedRef) Log(ctx context.Context) (*CommitCursor, error) {
	panic("not implemented")
}

func (ref *UpdatedRef) Diff(ctx context.Context) (*string, error) {
	panic("not implemented")
}
