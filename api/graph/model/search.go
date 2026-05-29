package model

import (
	"git.sr.ht/~sircmpwn/core-go/model"
)

// Results from a code search.
//
// If there are additional results available, the cursor object may be passed
// back into the same endpoint to retrieve another page. If the cursor is null,
// there are no remaining results to return.
type CodeSearchCursor struct {
	TotalFiles   int           `json:"totalFiles"`
	TotalMatches int           `json:"totalMatches"`
	Results      []*FileMatch  `json:"results"`
	Cursor       *model.Cursor `json:"cursor,omitempty"`
}

// A file that was matched during a code search.
type FileMatch struct {
	// Detected source language
	Lang string `json:"lang"`
	// Name of matched file
	Name string `json:"name"`
	// Matching lines from this file
	Lines []*LineMatch `json:"lines"`
	// Ranking score. Higher is better.
	Score float64 `json:"score"`

	RepoID int
}

// A line of source code matched during a code search.
type LineMatch struct {
	// The line of source code matched
	Line   string `json:"line"`
	LineNo int    `json:"lineNo"`
	// Byte offset where the line appears
	StartOffset int `json:"startOffset"`
	// Byte offset following the final byte of the matched line
	EndOffset int `json:"endOffset"`
	// Lines of context before the matching line
	Before string `json:"before"`
	// Lines of context after the matching line
	After string `json:"after"`
	// Match score, used to rank matches within a file. Higher is better.
	Score     float64         `json:"score"`
	Fragments []*LineFragment `json:"fragments"`
}

// A line fragment indicates which portion of a line of a LineMatch matched the
// search terms.
type LineFragment struct {
	LineOffset int     `json:"lineOffset"`
	FileOffset uint32  `json:"fileOffset"`
	Length     int     `json:"length"`
	Symbol     *Symbol `json:"symbol,omitempty"`
}

type Symbol struct {
	Name string `json:"name"`
	Kind string `json:"kind"`
}
