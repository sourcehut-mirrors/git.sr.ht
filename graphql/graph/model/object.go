package model

import (
	"errors"
	"fmt"

	"github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/plumbing"
	"github.com/go-git/go-git/v5/plumbing/object"
)

type Object interface {
	IsObject()
}

func LookupObject(repo *git.Repository, hash plumbing.Hash) (Object, error) {
	obj, err := repo.Object(plumbing.AnyObject, hash)
	if err != nil {
		return nil, fmt.Errorf("lookup object %s: %w", hash.String(), err)
	}
	switch obj := obj.(type) {
	case *object.Commit:
		return &Commit{
			Type:    ObjectTypeCommit,
			ID:      obj.ID().String(),
			ShortID: obj.ID().String()[:7],

			commit:  obj,
		}, nil
	default:
		return nil, errors.New("Unknown object type")
	}
}

type Commit struct {
	Type      ObjectType `json:"type"`
	ID        string     `json:"id"`
	ShortID   string     `json:"shortId"`
	Raw       string     `json:"raw"`
	Tree      *Tree      `json:"tree"`
	Parents   []*Commit  `json:"parents"`

	commit *object.Commit
}

func (Commit) IsObject() {}

func (c *Commit) Message() string {
	return c.commit.Message
}

func (c *Commit) Author() *Signature {
	return &Signature{
		Name: c.commit.Author.Name,
		Email: c.commit.Author.Email,
		Time: c.commit.Author.When,
	}
}

func (c *Commit) Committer() *Signature {
	return &Signature{
		Name: c.commit.Committer.Name,
		Email: c.commit.Committer.Email,
		Time: c.commit.Committer.When,
	}
}
