package main

import (
	"encoding/base64"
	"io/ioutil"

	"github.com/go-git/go-git/v5/plumbing"
	"github.com/go-git/go-git/v5/plumbing/object"
)

type RepoContext struct {
	Id         int    `json:"id"`
	Name       string `json:"name"`
	Path       string `json:"path"`
	Visibility string `json:"visibility"`
}

type UserContext struct {
	CanonicalName string `json:"canonical_name"`
	Name          string `json:"name"`
}

type PushContext struct {
	Repo RepoContext `json:"repo"`
	User UserContext `json:"user"`
}

type AnnotatedTag struct {
	Name    string `json:"name"`
	Message string `json:"message"`
}

type CommitSignature struct {
	Data      string `json:"data"`
	Signature string `json:"signature"`
}

type CommitAuthorship struct {
	Email string `json:"email"`
	Name  string `json:"name"`
}

// See gitsrht/blueprints/api.py
type Commit struct {
	Id        string   `json:"id"`
	Message   string   `json:"message"`
	Parents   []string `json:"parents"`
	ShortId   string   `json:"short_id"`
	Timestamp string   `json:"timestamp"`
	Tree      string   `json:"tree"`

	Author    CommitAuthorship `json:"author"`
	Committer CommitAuthorship `json:"committer"`
	Signature *CommitSignature `json:"signature"`
}

func GitCommitToWebhookCommit(c *object.Commit) *Commit {
	parents := make([]string, len(c.ParentHashes))
	for i, p := range c.ParentHashes {
		parents[i] = p.String()
	}

	var signature *CommitSignature = nil
	if c.PGPSignature != "" {
		encoded := &plumbing.MemoryObject{}
		c.EncodeWithoutSignature(encoded)
		reader, _ := encoded.Reader()
		data, _ := ioutil.ReadAll(ioutil.NopCloser(reader))
		signature = &CommitSignature{
			Data:      base64.StdEncoding.EncodeToString(data),
			Signature: base64.StdEncoding.EncodeToString([]byte(c.PGPSignature)),
		}
	}

	return &Commit{
		Id:        c.Hash.String(),
		Message:   c.Message,
		Parents:   parents,
		ShortId:   c.Hash.String()[:7],
		Timestamp: c.Author.When.Format("2006-01-02T15:04:05-07:00"),
		Tree:      c.TreeHash.String(),
		Author: CommitAuthorship{
			// TODO: Add timestamp
			Name:  c.Author.Name,
			Email: c.Author.Email,
		},
		Committer: CommitAuthorship{
			Name:  c.Committer.Name,
			Email: c.Committer.Email,
		},
		Signature: signature,
	}
}
