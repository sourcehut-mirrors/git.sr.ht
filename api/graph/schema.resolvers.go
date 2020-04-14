package graph

// This file will be automatically regenerated based on the schema, any resolver implementations
// will be copied through when generating and any unknown code will be moved to the end.

import (
	"context"
	"database/sql"
	"fmt"
	"sort"
	"strings"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/auth"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/database"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/generated"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/model"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/loaders"
	"git.sr.ht/~sircmpwn/gqlgen/graphql"
	sq "github.com/Masterminds/squirrel"
	"github.com/go-git/go-git/v5/plumbing"
)

func (r *mutationResolver) CreateRepository(ctx context.Context, params *model.RepoInput) (*model.Repository, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *mutationResolver) UpdateRepository(ctx context.Context, id string, params *model.RepoInput) (*model.Repository, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *mutationResolver) DeleteRepository(ctx context.Context, id string) (*model.Repository, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *mutationResolver) UpdateACL(ctx context.Context, repoID string, mode model.AccessMode, entity string) (*model.ACL, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *mutationResolver) DeleteACL(ctx context.Context, repoID int, entity string) (*model.ACL, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *mutationResolver) UploadArtifact(ctx context.Context, repoID int, revspec string, file graphql.Upload) (*model.Artifact, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *mutationResolver) DeleteArtifact(ctx context.Context, id int) (*model.Artifact, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *queryResolver) Version(ctx context.Context) (*model.Version, error) {
	return &model.Version{
		Major:           0,
		Minor:           0,
		Patch:           0,
		DeprecationDate: nil,
	}, nil
}

func (r *queryResolver) Me(ctx context.Context) (*model.User, error) {
	user := auth.ForContext(ctx)
	return &model.User{
		ID:       user.ID,
		Created:  user.Created,
		Updated:  user.Updated,
		Username: user.Username,
		Email:    user.Email,
		URL:      user.URL,
		Location: user.Location,
		Bio:      user.Bio,
	}, nil
}

func (r *queryResolver) User(ctx context.Context, username string) (*model.User, error) {
	return loaders.ForContext(ctx).UsersByName.Load(username)
}

func (r *queryResolver) Repositories(ctx context.Context, next *int, filter *model.FilterBy) ([]*model.Repository, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *queryResolver) Repository(ctx context.Context, id int) (*model.Repository, error) {
	return loaders.ForContext(ctx).RepositoriesByID.Load(id)
}

func (r *queryResolver) RepositoryByName(ctx context.Context, name string) (*model.Repository, error) {
	return loaders.ForContext(ctx).RepositoriesByName.Load(name)
}

func (r *queryResolver) RepositoryByOwner(ctx context.Context, owner string, repo string) (*model.Repository, error) {
	if strings.HasPrefix(owner, "~") {
		owner = owner[1:]
	} else {
		return nil, fmt.Errorf("Expected owner to be a canonical name")
	}
	return loaders.ForContext(ctx).
		RepositoriesByOwnerRepoName.Load([2]string{owner, repo})
}

func (r *repositoryResolver) Owner(ctx context.Context, obj *model.Repository) (model.Entity, error) {
	return loaders.ForContext(ctx).UsersByID.Load(obj.OwnerID)
}

func (r *repositoryResolver) AccessControlList(ctx context.Context, obj *model.Repository, count *int, next *int) ([]*model.ACL, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *repositoryResolver) References(ctx context.Context, obj *model.Repository, count *int, next *string, glob *string) ([]*model.Reference, error) {
	iter, err := obj.Repo().References()
	if err != nil {
		return nil, err
	}
	defer iter.Close()
	var refs []*model.Reference
	iter.ForEach(func(ref *plumbing.Reference) error {
		refs = append(refs, &model.Reference{obj.Repo(), ref})
		return nil
	})
	// TODO: Implement globbing
	sort.SliceStable(refs, func(i, j int) bool {
		return refs[i].Name() < refs[j].Name()
	})
	if next != nil {
		for i, ref := range refs {
			if ref.Name() == *next {
				refs = refs[i+1:]
				if len(refs) > *count {
					refs = refs[:*count]
				}
				return refs, nil
			}
		}
	}
	if len(refs) > *count {
		refs = refs[:*count]
	}
	return refs, nil
}

func (r *userResolver) Repositories(ctx context.Context, obj *model.User, count *int, next *int, filter *model.FilterBy) ([]*model.Repository, error) {
	var (
		err  error
		rows *sql.Rows
	)
	query := database.
		Select(ctx, (&model.Repository{}).As(`repo`)).
		From(`repository repo`).
		Where(sq.And{
			sq.Expr(`repo.owner_id = ?`, obj.ID),
			sq.Expr(`CASE WHEN ? != 0 THEN repo.id < ? ELSE true END`, next, next),
		}).
		OrderBy(`id DESC`).
		Limit(uint64(*count))
	if rows, err = query.RunWith(r.DB).QueryContext(ctx); err != nil {
		panic(err)
	}
	defer rows.Close()
	var repos []*model.Repository
	for rows.Next() {
		var repo model.Repository
		if err := rows.Scan(repo.Fields(ctx)...); err != nil {
			panic(err)
		}
		repos = append(repos, &repo)
	}
	return repos, nil
}

// Mutation returns generated.MutationResolver implementation.
func (r *Resolver) Mutation() generated.MutationResolver { return &mutationResolver{r} }

// Query returns generated.QueryResolver implementation.
func (r *Resolver) Query() generated.QueryResolver { return &queryResolver{r} }

// Repository returns generated.RepositoryResolver implementation.
func (r *Resolver) Repository() generated.RepositoryResolver { return &repositoryResolver{r} }

// User returns generated.UserResolver implementation.
func (r *Resolver) User() generated.UserResolver { return &userResolver{r} }

type mutationResolver struct{ *Resolver }
type queryResolver struct{ *Resolver }
type repositoryResolver struct{ *Resolver }
type userResolver struct{ *Resolver }
