package model

import (
	"github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/plumbing/object"
)

type Commit struct {
	Type    ObjectType `json:"type"`
	ID      string     `json:"id"`
	ShortID string     `json:"shortId"`
	Raw     string     `json:"raw"`

	commit *object.Commit
	repo   *git.Repository
}

func (Commit) IsObject() {}

func (c *Commit) Message() string {
	return c.commit.Message
}

func (c *Commit) Author() *Signature {
	return &Signature{
		Name:  c.commit.Author.Name,
		Email: c.commit.Author.Email,
		Time:  c.commit.Author.When,
	}
}

func (c *Commit) Committer() *Signature {
	return &Signature{
		Name:  c.commit.Committer.Name,
		Email: c.commit.Committer.Email,
		Time:  c.commit.Committer.When,
	}
}

func (c *Commit) Tree() *Tree {
	obj, err := LookupObject(c.repo, c.commit.TreeHash)
	if err != nil {
		panic(err)
	}
	tree, _ := obj.(*Tree)
	return tree
}

func (c *Commit) Parents() []*Commit {
	var parents []*Commit
	for _, p := range c.commit.ParentHashes {
		obj, err := LookupObject(c.repo, p)
		if err != nil {
			panic(err)
		}
		parent, _ := obj.(*Commit)
		parents = append(parents, parent)
	}
	return parents
}
