package search

import (
	"context"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/model"

	"git.sr.ht/~sircmpwn/core-go/errors"
	coremodel "git.sr.ht/~sircmpwn/core-go/model"
	"github.com/sourcegraph/zoekt"
	zquery "github.com/sourcegraph/zoekt/query"
)

func SearchRepo(
	ctx context.Context,
	repo *model.Repository,
	cursor *coremodel.Cursor,
	query string,
) (*model.CodeSearchCursor, error) {
	sctx, ok := ctx.Value(ctxKey).(*SearchContext)
	if !ok {
		return nil, errors.New(errors.Unsupported,
			"Code search is not enabled on this instance")
	}

	q, err := zquery.Parse(query)
	if err != nil {
		return nil, err
	}
	q = zquery.NewAnd(q, zquery.NewRepoIDs(uint32(repo.ID)))

	result, err := sctx.index.Search(ctx, q, &zoekt.SearchOptions{
		NumContextLines:    3,
		TotalMaxMatchCount: 50,
		MaxDocDisplayCount: 20,
	})
	if err != nil {
		return nil, err
	}

	return modelResults(repo, result), nil
}

func modelResults(repo *model.Repository, result *zoekt.SearchResult) *model.CodeSearchCursor {
	outcome := &model.CodeSearchCursor{
		TotalFiles:   result.FileCount,
		TotalMatches: result.MatchCount,
		Results:      make([]*model.FileMatch, len(result.Files)),
		Cursor:       nil, // TODO
	}

	for i, file := range result.Files {
		lines := make([]*model.LineMatch, len(file.LineMatches))

		for i, match := range file.LineMatches {
			fragments := make([]*model.LineFragment, len(match.LineFragments))

			for i, frag := range match.LineFragments {
				fragments[i] = &model.LineFragment{
					LineOffset: frag.LineOffset,
					FileOffset: frag.Offset,
					Length:     frag.MatchLength,
				}
				if frag.SymbolInfo != nil {
					fragments[i].Symbol = &model.Symbol{
						Name: frag.SymbolInfo.Sym,
						Kind: frag.SymbolInfo.Kind,
					}
				}
			}

			lines[i] = &model.LineMatch{
				Line:        string(match.Line),
				LineNo:      match.LineNumber,
				StartOffset: match.LineStart,
				EndOffset:   match.LineEnd,
				Before:      string(match.Before),
				After:       string(match.After),
				Score:       match.Score,
			}
		}

		outcome.Results[i] = &model.FileMatch{
			Name:   file.FileName,
			Lang:   file.Language,
			Score:  file.Score,
			Lines:  lines,
			RepoID: repo.ID,
		}
	}

	return outcome
}
