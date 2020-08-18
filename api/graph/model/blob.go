package model

import (
	"encoding/base64"
	"io/ioutil"
	"unicode/utf8"

	"github.com/go-git/go-git/v5/plumbing/object"
)

type BinaryBlob struct {
	Type    ObjectType `json:"type"`
	ID      string     `json:"id"`
	ShortID string     `json:"shortId"`
	Raw     string     `json:"raw"`

	Base64 string `json:"base64"`

	blob  *object.Blob
	repo  *RepoWrapper
}

func (BinaryBlob) IsObject() {}
func (BinaryBlob) IsBlob() {}

type TextBlob struct {
	Type    ObjectType `json:"type"`
	ID      string     `json:"id"`
	ShortID string     `json:"shortId"`
	Raw     string     `json:"raw"`

	Text string `json:"text"`

	blob  *object.Blob
	repo  *RepoWrapper
}

func (TextBlob) IsObject() {}
func (TextBlob) IsBlob() {}

func BlobFromObject(repo *RepoWrapper, obj *object.Blob) Object {
	reader, err := obj.Reader()
	if err != nil {
		panic(err)
	}
	defer reader.Close()

	// XXX: Probably a bad idea
	// An improvement would be to just read the first bit, and see if it's
	// parsable as UTF-8, then wait to fetch the rest until the user asks for
	// it (or, if they ask for a range, we might skip some!). This would still
	// be kind of finicky though, because if we accidentally read half of a
	// UTF-8 codepoint at the end of the buffer, we'll be in Problems City,
	// population us.
	bytes, err := ioutil.ReadAll(reader)
	if err != nil {
		panic(err)
	}

	text := string(bytes)
	if utf8.ValidString(text) {
		return &TextBlob{
			Type:    ObjectTypeBlob,
			ID:      obj.ID().String(),
			ShortID: obj.ID().String()[:7],
			Text:    text,

			blob: obj,
			repo: repo,
		}
	} else {
		b64 := base64.StdEncoding.EncodeToString(bytes)
		return &BinaryBlob{
			Type:    ObjectTypeBlob,
			ID:      obj.ID().String(),
			ShortID: obj.ID().String()[:7],
			Base64:  b64,

			blob: obj,
			repo: repo,
		}
	}
}
