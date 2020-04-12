package graph

// This file will be automatically regenerated based on the schema, any resolver implementations
// will be copied through when generating and any unknown code will be moved to the end.

import (
	"context"
	"database/sql"
	"fmt"

	"git.sr.ht/~sircmpwn/git.sr.ht/graphql/auth"
	"git.sr.ht/~sircmpwn/git.sr.ht/graphql/graph/generated"
	"git.sr.ht/~sircmpwn/git.sr.ht/graphql/graph/model"
	"git.sr.ht/~sircmpwn/git.sr.ht/graphql/loaders"
	"git.sr.ht/~sircmpwn/gqlgen/graphql"
)

func (r *mutationResolver) CreateRepository(ctx context.Context, params *model.RepoInput) (*model.Repository, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *mutationResolver) UpdateRepository(ctx context.Context, id model.RepoID, params *model.RepoInput) (*model.Repository, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *mutationResolver) DeleteRepository(ctx context.Context, id model.RepoID) (*model.Repository, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *mutationResolver) UpdateACL(ctx context.Context, id model.RepoID, mode model.AccessMode, entity model.EntityID) (*model.ACL, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *mutationResolver) DeleteACL(ctx context.Context, id model.RepoID, entity model.EntityID) (*model.ACL, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *mutationResolver) UploadArtifact(ctx context.Context, id model.RepoID, revspec string, file graphql.Upload) (*model.Artifact, error) {
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
		ID:       user.Id,
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
	panic(fmt.Errorf("not implemented"))
}

func (r *queryResolver) Repositories(ctx context.Context, next *int, filter *model.FilterBy) ([]*model.Repository, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *queryResolver) Repository(ctx context.Context, id *model.RepoID) (*model.Repository, error) {
	panic(fmt.Errorf("not implemented"))
}

func (r *repositoryResolver) Owner(ctx context.Context, obj *model.Repository) (model.Entity, error) {
	return loaders.ForContext(ctx).UsersById.Load(obj.OwnerID)
}

func (r *userResolver) Repositories(ctx context.Context, obj *model.User, count *int, next *int, filter *model.FilterBy) ([]*model.Repository, error) {
	var (
		err  error
		rows *sql.Rows
	)
	if rows, err = r.DB.QueryContext(ctx, `
			SELECT
				repo.id,
				repo.created, repo.updated,
				repo.name, repo.description,
				repo.owner_id,
				repo.path,
				repo.visibility,
				repo.upstream_uri
			FROM repository repo
			WHERE
				repo.owner_id = $1
				AND CASE WHEN $2 != 0 THEN repo.id < $2 ELSE true END
			ORDER BY id DESC
			LIMIT $3;
		`, obj.ID, next, count); err != nil {
		panic(err)
	}
	defer rows.Close()
	var repos []*model.Repository
	for rows.Next() {
		var repo model.Repository
		if err := rows.Scan(&repo.ID,
			&repo.Created, &repo.Updated,
			&repo.Name, &repo.Description,
			&repo.OwnerID,
			&repo.Path,
			&repo.Visibility,
			&repo.UpstreamURL); err != nil {
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
