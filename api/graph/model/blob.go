package model

import (
	"io"
	"unicode/utf8"

	"github.com/go-git/go-git/v5/plumbing/object"
)

type BinaryBlob struct {
	Type    ObjectType `json:"type"`
	ID      string     `json:"id"`
	ShortID string     `json:"shortId"`
	Size    int64      `json:"size"`

	Repo *RepoWrapper
	Blob *object.Blob
}

func (BinaryBlob) IsObject() {}
func (BinaryBlob) IsBlob()   {}

type TextBlob struct {
	Type    ObjectType `json:"type"`
	ID      string     `json:"id"`
	ShortID string     `json:"shortId"`
	Size    int64      `json:"size"`

	Repo *RepoWrapper
	Blob *object.Blob
}

func (TextBlob) IsObject() {}
func (TextBlob) IsBlob()   {}

func BlobFromObject(repo *RepoWrapper, obj *object.Blob) Object {
	reader, err := obj.Reader()
	if err != nil {
		panic(err)
	}
	defer reader.Close()

	// Determine if the content is valid UTF-8. We only check the start of
	// the blob and assume the rest is similar.
	var data [512]byte
	n, err := reader.Read(data[:])
	if err == io.EOF {
		n = 0
	} else if err != nil {
		panic(err)
	}

	valid := true
	for i := 0; i < n; {
		r, l := utf8.DecodeRune(data[i:])
		if r == utf8.RuneError {
			// Suppose the file is valid UTF-8 if the end of our
			// 512 byte buffer has a truncated sequence
			valid =
				utf8.RuneStart(data[i]) &&
					i >= n-utf8.UTFMax
			break
		}
		i += l
	}

	if n == 0 || valid {
		return &TextBlob{
			Type:    ObjectTypeBlob,
			ID:      obj.ID().String(),
			ShortID: obj.ID().String()[:7],
			Size:    obj.Size,
			Repo:    repo,
			Blob:    obj,
		}
	} else {
		return &BinaryBlob{
			Type:    ObjectTypeBlob,
			ID:      obj.ID().String(),
			ShortID: obj.ID().String()[:7],
			Size:    obj.Size,
			Repo:    repo,
			Blob:    obj,
		}
	}
}
