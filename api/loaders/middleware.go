package loaders

import (
	"context"
	"database/sql"
	"errors"
	"net/http"
	"time"

	sq "github.com/Masterminds/squirrel"
	"github.com/lib/pq"

	"git.sr.ht/~sircmpwn/core-go/auth"
	"git.sr.ht/~sircmpwn/core-go/database"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/model"
)

var loadersCtxKey = &contextKey{"loaders"}

type contextKey struct {
	name string
}

type Loaders struct {
	UsersByID                   UsersByIDLoader
	UsersByName                 UsersByNameLoader
	RepositoriesByID            RepositoriesByIDLoader
	RepositoriesByName          RepositoriesByNameLoader
	RepositoriesByOwnerRepoName RepositoriesByOwnerRepoNameLoader
}

func fetchUsersByID(ctx context.Context) func(ids []int) ([]*model.User, []error) {
	return func(ids []int) ([]*model.User, []error) {
		users := make([]*model.User, len(ids))
		if err := database.WithTx(ctx, &sql.TxOptions{
			Isolation: 0,
			ReadOnly:  true,
		}, func(tx *sql.Tx) error {
			var (
				err  error
				rows *sql.Rows
			)
			query := database.
				Select(ctx, (&model.User{}).As(`u`)).
				From(`"user" u`).
				Where(sq.Expr(`u.id = ANY(?)`, pq.Array(ids)))
			if rows, err = query.RunWith(tx).QueryContext(ctx); err != nil {
				panic(err)
			}
			defer rows.Close()

			usersById := map[int]*model.User{}
			for rows.Next() {
				var user model.User
				if err := rows.Scan(database.Scan(ctx, &user)...); err != nil {
					panic(err)
				}
				usersById[user.ID] = &user
			}
			if err = rows.Err(); err != nil {
				panic(err)
			}

			for i, id := range ids {
				users[i] = usersById[id]
			}
			return nil
		}); err != nil {
			panic(err)
		}
		return users, nil
	}
}

func fetchUsersByName(ctx context.Context) func(names []string) ([]*model.User, []error) {
	return func(names []string) ([]*model.User, []error) {
		users := make([]*model.User, len(names))
		if err := database.WithTx(ctx, &sql.TxOptions{
			Isolation: 0,
			ReadOnly:  true,
		}, func(tx *sql.Tx) error {
			var (
				err  error
				rows *sql.Rows
			)
			query := database.
				Select(ctx, (&model.User{}).As(`u`)).
				From(`"user" u`).
				Where(sq.Expr(`u.username = ANY(?)`, pq.Array(names)))
			if rows, err = query.RunWith(tx).QueryContext(ctx); err != nil {
				panic(err)
			}
			defer rows.Close()

			usersByName := map[string]*model.User{}
			for rows.Next() {
				user := model.User{}
				if err := rows.Scan(database.Scan(ctx, &user)...); err != nil {
					panic(err)
				}
				usersByName[user.Username] = &user
			}
			if err = rows.Err(); err != nil {
				panic(err)
			}

			for i, name := range names {
				users[i] = usersByName[name]
			}
			return nil
		}); err != nil {
			panic(err)
		}
		return users, nil
	}
}

func fetchRepositoriesByID(ctx context.Context) func(ids []int) ([]*model.Repository, []error) {
	return func(ids []int) ([]*model.Repository, []error) {
		repos := make([]*model.Repository, len(ids))
		if err := database.WithTx(ctx, &sql.TxOptions{
			Isolation: 0,
			ReadOnly:  true,
		}, func(tx *sql.Tx) error {
			var (
				err  error
				rows *sql.Rows
			)
			auser := auth.ForContext(ctx)
			query := database.
				Select(ctx, (&model.Repository{}).As(`repo`)).
				Distinct().
				From(`repository repo`).
				LeftJoin(`access ON repo.id = access.repo_id`).
				Where(sq.And{
					sq.Expr(`repo.id = ANY(?)`, pq.Array(ids)),
					sq.Or{
						sq.Expr(`? IN (access.user_id, repo.owner_id)`, auser.UserID),
						sq.Expr(`repo.visibility != 'private'`),
					},
				})
			if rows, err = query.RunWith(tx).QueryContext(ctx); err != nil {
				panic(err)
			}
			defer rows.Close()

			reposById := map[int]*model.Repository{}
			for rows.Next() {
				repo := model.Repository{}
				if err := rows.Scan(database.Scan(ctx, &repo)...); err != nil {
					panic(err)
				}
				reposById[repo.ID] = &repo
			}
			if err = rows.Err(); err != nil {
				panic(err)
			}

			for i, id := range ids {
				repos[i] = reposById[id]
			}
			return nil
		}); err != nil {
			panic(err)
		}
		return repos, nil
	}
}

func fetchRepositoriesByName(ctx context.Context) func(names []string) ([]*model.Repository, []error) {
	return func(names []string) ([]*model.Repository, []error) {
		repos := make([]*model.Repository, len(names))
		if err := database.WithTx(ctx, &sql.TxOptions{
			Isolation: 0,
			ReadOnly:  true,
		}, func(tx *sql.Tx) error {
			var (
				err  error
				rows *sql.Rows
			)
			query := database.
				Select(ctx, (&model.Repository{}).As(`repo`)).
				Distinct().
				From(`repository repo`).
				Where(sq.And{
					sq.Expr(`repo.name = ANY(?)`, pq.Array(names)),
					sq.Expr(`repo.owner_id = ?`, auth.ForContext(ctx).UserID),
				})
			if rows, err = query.RunWith(tx).QueryContext(ctx); err != nil {
				panic(err)
			}
			defer rows.Close()

			reposByName := map[string]*model.Repository{}
			for rows.Next() {
				repo := model.Repository{}
				if err := rows.Scan(database.Scan(ctx, &repo)...); err != nil {
					panic(err)
				}
				reposByName[repo.Name] = &repo
			}
			if err = rows.Err(); err != nil {
				panic(err)
			}

			for i, name := range names {
				repos[i] = reposByName[name]
			}
			return nil
		}); err != nil {
			panic(err)
		}
		return repos, nil
	}
}

func fetchRepositoriesByOwnerRepoName(ctx context.Context) func(names [][2]string) ([]*model.Repository, []error) {
	return func(names [][2]string) ([]*model.Repository, []error) {
		repos := make([]*model.Repository, len(names))
		if err := database.WithTx(ctx, &sql.TxOptions{
			Isolation: 0,
			ReadOnly:  true,
		}, func(tx *sql.Tx) error {
			var (
				err    error
				rows   *sql.Rows
				_names []string = make([]string, len(names))
			)
			for i, name := range names {
				// This is a hack, but it works around limitations with PostgreSQL
				// and is guaranteed to work because / is invalid in both usernames
				// and repo names
				_names[i] = name[0] + "/" + name[1]
			}
			query := database.
				Select(ctx).
				Prefix(`WITH user_repo AS (
					SELECT
						substring(un for position('/' in un)-1) AS owner,
						substring(un from position('/' in un)+1) AS repo
					FROM unnest(?::text[]) un)`, pq.Array(_names)).
				Columns(database.Columns(ctx, (&model.Repository{}).As(`repo`))...).
				Columns(`u.username`).
				Distinct().
				From(`user_repo ur`).
				Join(`"user" u on ur.owner = u.username`).
				Join(`repository repo ON ur.repo = repo.name
					AND u.id = repo.owner_id`).
				LeftJoin(`access ON repo.id = access.repo_id`).
				Where(sq.Or{
					sq.Expr(`? IN (access.user_id, repo.owner_id)`,
						auth.ForContext(ctx).UserID),
					sq.Expr(`repo.visibility != 'private'`),
				})
			if rows, err = query.RunWith(tx).QueryContext(ctx); err != nil {
				panic(err)
			}
			defer rows.Close()

			reposByOwnerRepoName := map[[2]string]*model.Repository{}
			for rows.Next() {
				var ownerName string
				repo := model.Repository{}
				if err := rows.Scan(append(
					database.Scan(ctx, &repo), &ownerName)...); err != nil {
					panic(err)
				}
				reposByOwnerRepoName[[2]string{ownerName, repo.Name}] = &repo
			}
			if err = rows.Err(); err != nil {
				panic(err)
			}

			for i, name := range names {
				repos[i] = reposByOwnerRepoName[name]
			}
			return nil
		}); err != nil {
			panic(err)
		}
		return repos, nil
	}
}

func Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx := context.WithValue(r.Context(), loadersCtxKey, &Loaders{
			UsersByID: UsersByIDLoader{
				maxBatch: 100,
				wait:     1 * time.Millisecond,
				fetch:    fetchUsersByID(r.Context()),
			},
			UsersByName: UsersByNameLoader{
				maxBatch: 100,
				wait:     1 * time.Millisecond,
				fetch:    fetchUsersByName(r.Context()),
			},
			RepositoriesByID: RepositoriesByIDLoader{
				maxBatch: 100,
				wait:     1 * time.Millisecond,
				fetch:    fetchRepositoriesByID(r.Context()),
			},
			RepositoriesByName: RepositoriesByNameLoader{
				maxBatch: 100,
				wait:     1 * time.Millisecond,
				fetch:    fetchRepositoriesByName(r.Context()),
			},
			RepositoriesByOwnerRepoName: RepositoriesByOwnerRepoNameLoader{
				maxBatch: 100,
				wait:     1 * time.Millisecond,
				fetch:    fetchRepositoriesByOwnerRepoName(r.Context()),
			},
		})
		r = r.WithContext(ctx)
		next.ServeHTTP(w, r)
	})
}

func ForContext(ctx context.Context) *Loaders {
	raw, ok := ctx.Value(loadersCtxKey).(*Loaders)
	if !ok {
		panic(errors.New("Invalid data loaders context"))
	}
	return raw
}
