package model

import "time"

type Repository struct {
	ID                int          `json:"id"`
	Created           time.Time    `json:"created"`
	Updated           time.Time    `json:"updated"`
	Name              string       `json:"name"`
	Description       *string      `json:"description"`
	Visibility        Visibility   `json:"visibility"`
	UpstreamURL       *string      `json:"upstreamUrl"`
	AccessControlList []*ACL       `json:"accessControlList"`
	References        []*Reference `json:"references"`
	Objects           []Object     `json:"objects"`
	Head              *Reference   `json:"head"`
	Log               []*Commit    `json:"log"`
	Tree              *Tree        `json:"tree"`
	File              *Blob        `json:"file"`
	RevparseSingle    Object       `json:"revparse_single"`

	Path    string
	OwnerID int
}
