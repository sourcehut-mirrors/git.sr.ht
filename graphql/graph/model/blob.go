package model

import (
	"errors"
	"io/ioutil"
	"unicode/utf8"

	"github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/plumbing/object"
)

type Blob struct {
	Type     ObjectType `json:"type"`
	ID       string     `json:"id"`
	ShortID  string     `json:"shortId"`
	Raw      string     `json:"raw"`

	blob  *object.Blob
	repo  *git.Repository
	bytes []byte
}

func (Blob) IsObject() {}

type BlobData interface {
	IsBlobData()
}

type BinaryBlob struct {
	Base64 string `json:"base64"`
}

func (BinaryBlob) IsBlobData() {}

type TextBlob struct {
	Text string `json:"text"`
}

func (TextBlob) IsBlobData() {}

func (blob *Blob) Bytes() []byte {
	if blob.bytes != nil {
		return blob.bytes
	}
	reader, err := blob.blob.Reader()
	if err != nil {
		panic(err)
	}
	defer reader.Close()
	// XXX: Probably a bad idea
	blob.bytes, err = ioutil.ReadAll(reader)
	if err != nil {
		panic(err)
	}
	return blob.bytes
}

func (blob *Blob) BlobType() BlobType {
	if utf8.ValidString(string(blob.Bytes())) {
		return BlobTypeText
	} else {
		return BlobTypeBinary
	}
}

func (blob *Blob) Data() BlobData {
	switch blob.BlobType() {
	case BlobTypeBinary:
		panic(errors.New("Unimplemented"))
	case BlobTypeText:
		return &TextBlob{Text: string(blob.Bytes())}
	default:
		panic(errors.New("Unknown blob type"))
	}
}
