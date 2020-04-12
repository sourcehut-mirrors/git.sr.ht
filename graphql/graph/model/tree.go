package model

import (
	"sort"

	"github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/plumbing"
	"github.com/go-git/go-git/v5/plumbing/object"
)

type Tree struct {
	Type    ObjectType   `json:"type"`
	ID      string       `json:"id"`
	ShortID string       `json:"shortId"`
	Raw     string       `json:"raw"`

	tree *object.Tree
	repo *git.Repository
}

func (Tree) IsObject() {}

type TreeEntry struct {
	Name   string `json:"name"`
	Mode   int    `json:"mode"`

	hash plumbing.Hash
	repo *git.Repository
}

func (ent *TreeEntry) ID() string {
	return ent.hash.String()
}

func (ent *TreeEntry) Object() Object {
	obj, err := LookupObject(ent.repo, ent.hash)
	if err != nil {
		panic(err)
	}
	return obj
}

func (tree *Tree) Entries(count *int, next *string) []*TreeEntry {
	entries := tree.tree.Entries[:]
	sort.SliceStable(entries, func(a, b int) bool {
		return entries[a].Name < entries[b].Name
	})

	qlents := make([]*TreeEntry, len(entries))
	for i, ent := range entries {
		qlents[i] = &TreeEntry{
			Name: ent.Name,
			Mode: int(ent.Mode),
			hash: ent.Hash,
			repo: tree.repo,
		}
	}

	if next != nil {
		for i, ent := range qlents {
			if ent.Name == *next {
				qlents = qlents[i+1:]
				if len(entries) > *count {
					qlents = qlents[:*count]
				}
				return qlents
			}
		}
	}
	if len(qlents) > *count {
		qlents = qlents[:*count]
	}
	return qlents
}

func (tree *Tree) Entry(path string) *TreeEntry {
	ent, err := tree.tree.FindEntry(path)
	if err == object.ErrEntryNotFound {
		return nil
	}
	return &TreeEntry{
		Name: ent.Name,
		Mode: int(ent.Mode),
		hash: ent.Hash,
		repo: tree.repo,
	}
}
