package model

import (
	"sort"

	"github.com/go-git/go-git/v5/plumbing"
	"github.com/go-git/go-git/v5/plumbing/object"
)

type Tree struct {
	Type    ObjectType `json:"type"`
	ID      string     `json:"id"`
	ShortID string     `json:"shortId"`
	Raw     string     `json:"raw"`

	tree *object.Tree
	repo *RepoWrapper
}

func (Tree) IsObject() {}

type TreeEntry struct {
	Name string `json:"name"`
	Mode int    `json:"mode"`

	hash plumbing.Hash
	repo *RepoWrapper
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

func (tree *Tree) GetEntries() []*TreeEntry {
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

	return qlents
}

func TreeFromObject(repo *RepoWrapper, obj *object.Tree) *Tree {
	return &Tree{
		Type:    ObjectTypeTree,
		ID:      obj.ID().String(),
		ShortID: obj.ID().String()[:7],

		tree: obj,
		repo: repo,
	}
}
