package graph

// This file will be automatically regenerated based on the schema, any resolver implementations
// will be copied through when generating and any unknown code will be moved to the end.

import (
	"context"
	"fmt"
	"sort"
	"strings"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/auth"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/database"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/generated"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/model"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/loaders"
	"git.sr.ht/~sircmpwn/gqlgen/graphql"
	"github.com/go-git/go-git/v5/plumbing"
)

func (r *aCLResolver) Repository(ctx context.Context, obj *model.ACL) (*model.Repository, error) {
	// XXX This could be moved into a loader, but it's unlikely to be a
	// frequently utilized endpoint, so I'm not especially interested in the
	// extra work/cruft.
	repo := (&model.Repository{}).As(`repo`)
	query := database.
		Select(ctx, repo).
		From(`repository repo`).
		Join(`access acl ON acl.repo_id = repo.id`).
		Where(`acl.id = ?`, obj.ID)
	row := query.RunWith(r.DB).QueryRow()
	if err := row.Scan(repo.Fields(ctx)...); err != nil {
		panic(err)
	}
	return repo, nil
}

func (r *aCLResolver) Entity(ctx context.Context, obj *model.ACL) (model.Entity, error) {
	// XXX This could be moved into a loader, but it's unlikely to be a
	// frequently utilized endpoint, so I'm not especially interested in the
	// extra work/cruft.
	user := (&model.User{}).As(`u`)
	query := database.
		Select(ctx, user).
		From(`"user" u`).
		Join(`access acl ON acl.user_id = u.id`).
		Where(`acl.id = ?`, obj.ID)
	row := query.RunWith(r.DB).QueryRow()
	if err := row.Scan(user.Fields(ctx)...); err != nil {
		panic(err)
	}
	return user, nil
}

func (r *mutationResolver) CreateRepository(ctx context.Context, params *model.RepoInput) (*model.Repository, error) {
	panic(fmt.Errorf("createRepository: not implemented"))
}

func (r *mutationResolver) UpdateRepository(ctx context.Context, id string, params *model.RepoInput) (*model.Repository, error) {
	panic(fmt.Errorf("updateRepository: not implemented"))
}

func (r *mutationResolver) DeleteRepository(ctx context.Context, id string) (*model.Repository, error) {
	panic(fmt.Errorf("deleteRepository: not implemented"))
}

func (r *mutationResolver) UpdateACL(ctx context.Context, repoID string, mode model.AccessMode, entity string) (*model.ACL, error) {
	panic(fmt.Errorf("updateACL: not implemented"))
}

func (r *mutationResolver) DeleteACL(ctx context.Context, repoID int, entity string) (*model.ACL, error) {
	panic(fmt.Errorf("deleteACL: not implemented"))
}

func (r *mutationResolver) UploadArtifact(ctx context.Context, repoID int, revspec string, file graphql.Upload) (*model.Artifact, error) {
	panic(fmt.Errorf("uploadArtifact: not implemented"))
}

func (r *mutationResolver) DeleteArtifact(ctx context.Context, id int) (*model.Artifact, error) {
	panic(fmt.Errorf("deleteArtifact: not implemented"))
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

func (r *queryResolver) Repositories(ctx context.Context, cursor *model.Cursor, filter *model.Filter) (*model.RepositoryCursor, error) {
	if cursor == nil {
		cursor = model.NewCursor(filter)
	}

	repo := (&model.Repository{}).As(`repo`)
	query := database.
		Select(ctx, repo).
		From(`repository repo`).
		Where(`repo.owner_id = ?`, auth.ForContext(ctx).ID)

	repos, cursor := repo.QueryWithCursor(ctx, r.DB, query, cursor)
	return &model.RepositoryCursor{repos, cursor}, nil
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

func (r *repositoryResolver) AccessControlList(ctx context.Context, obj *model.Repository, cursor *model.Cursor) (*model.ACLCursor, error) {
	if cursor == nil {
		cursor = model.NewCursor(nil)
	}

	acl := (&model.ACL{}).As(`acl`)
	query := database.
		Select(ctx, acl).
		From(`access acl`).
		Join(`repository repo ON acl.repo_id = repo.id`).
		Where(`acl.repo_id = ?`, obj.ID).
		Where(`repo.owner_id = ?`, auth.ForContext(ctx).ID)

	acls, cursor := acl.QueryWithCursor(ctx, r.DB, query, cursor)
	return &model.ACLCursor{acls, cursor}, nil
}

func (r *repositoryResolver) References(ctx context.Context, obj *model.Repository, cursor *model.Cursor) (*model.ReferenceCursor, error) {
	iter, err := obj.Repo().References()
	if err != nil {
		return nil, err
	}
	defer iter.Close()

	if cursor == nil {
		cursor = model.NewCursor(nil)
	}

	var refs []*model.Reference
	iter.ForEach(func(ref *plumbing.Reference) error {
		refs = append(refs, &model.Reference{obj.Repo(), ref})
		return nil
	})

	sort.SliceStable(refs, func(i, j int) bool {
		return refs[i].Name() < refs[j].Name()
	})

	// TODO: Implement cursor globbing/next

	if len(refs) > cursor.Count {
		cursor = &model.Cursor{
			Count:  cursor.Count,
			Next:   refs[len(refs)-1].Name(),
			Search: cursor.Search,
		}
		refs = refs[:cursor.Count]
	} else {
		cursor = nil
	}

	return &model.ReferenceCursor{refs, cursor}, nil
}

func (r *treeResolver) Entries(ctx context.Context, obj *model.Tree, cursor *model.Cursor) ([]*model.TreeEntry, error) {
	panic(fmt.Errorf("tree.entries: not implemented"))
}

func (r *userResolver) Repositories(ctx context.Context, obj *model.User, cursor *model.Cursor, filter *model.Filter) (*model.RepositoryCursor, error) {
	if cursor == nil {
		cursor = model.NewCursor(filter)
	}

	repo := (&model.Repository{}).As(`repo`)
	query := database.
		Select(ctx, repo).
		From(`repository repo`).
		Where(`repo.owner_id = ?`, obj.ID)

	repos, cursor := repo.QueryWithCursor(ctx, r.DB, query, cursor)
	return &model.RepositoryCursor{repos, cursor}, nil
}

// ACL returns generated.ACLResolver implementation.
func (r *Resolver) ACL() generated.ACLResolver { return &aCLResolver{r} }

// Mutation returns generated.MutationResolver implementation.
func (r *Resolver) Mutation() generated.MutationResolver { return &mutationResolver{r} }

// Query returns generated.QueryResolver implementation.
func (r *Resolver) Query() generated.QueryResolver { return &queryResolver{r} }

// Repository returns generated.RepositoryResolver implementation.
func (r *Resolver) Repository() generated.RepositoryResolver { return &repositoryResolver{r} }

// Tree returns generated.TreeResolver implementation.
func (r *Resolver) Tree() generated.TreeResolver { return &treeResolver{r} }

// User returns generated.UserResolver implementation.
func (r *Resolver) User() generated.UserResolver { return &userResolver{r} }

type aCLResolver struct{ *Resolver }
type mutationResolver struct{ *Resolver }
type queryResolver struct{ *Resolver }
type repositoryResolver struct{ *Resolver }
type treeResolver struct{ *Resolver }
type userResolver struct{ *Resolver }
