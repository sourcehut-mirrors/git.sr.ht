package search

import (
	"context"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path"
	"strconv"
	"strings"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/graph/model"

	"git.sr.ht/~sircmpwn/core-go/config"
	work "git.sr.ht/~sircmpwn/dowork"
	"github.com/sourcegraph/zoekt"
	"github.com/sourcegraph/zoekt/gitindex"
	"github.com/sourcegraph/zoekt/index"
	"github.com/sourcegraph/zoekt/search"
	"github.com/vaughan0/go-ini"
)

type contextKey struct {
	name string
}

var ctxKey = &contextKey{"search"}

type SearchContext struct {
	index    zoekt.Streamer
	indexDir string
	queue    *work.Queue
}

func Middleware(conf *ini.File, queue *work.Queue) func(next http.Handler) http.Handler {
	indexDir, ok := conf.Get("git.sr.ht", "repos-index")
	if !ok || indexDir == "" {
		// Code search disabled
		return nil
	}

	index, err := search.NewDirectorySearcherFast(indexDir)
	if err != nil {
		log.Printf("Error loading search index: %s", err.Error())
		return nil
	}

	searchContext := SearchContext{
		index:    index,
		indexDir: indexDir,
		queue:    queue,
	}

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := context.WithValue(r.Context(), ctxKey, &searchContext)
			r = r.WithContext(ctx)
			next.ServeHTTP(w, r)
		})
	}
}

// Returns true if code search is enabled.
func Enabled(ctx context.Context) bool {
	_, ok := ctx.Value(ctxKey).(*SearchContext)
	return ok
}

// Schedules a search index update for the given repository.
func Index(ctx context.Context, repo *model.Repository, ownerName string) {
	var err error

	sctx, ok := ctx.Value(ctxKey).(*SearchContext)
	if !ok {
		return
	}

	conf := config.ForContext(ctx)
	gitOrigin := config.GetOrigin(conf, "git.sr.ht", true)
	baseURL := fmt.Sprintf("%s/%s/%s", gitOrigin, ownerName, repo.Name)

	var public string
	if repo.Visibility == model.VisibilityPublic {
		public = "1"
	} else {
		public = "0"
	}

	opts := index.Options{}
	opts.SetDefaults()
	opts.IndexDir = sctx.indexDir
	opts.Parallelism = 4
	opts.ShardPrefixOverride = fmt.Sprintf("index_%010d", repo.ID)
	// Maximum shard size is 512 MiB
	opts.ShardMax = 512 * 1024 * 1024
	// Maximum size of one indexed file is 1 MiB
	opts.SizeMax = 1024 * 1024
	opts.RepositoryDescription = zoekt.Repository{
		Name:   fmt.Sprintf("%s/%s", ownerName, repo.Name),
		URL:    baseURL,
		Source: repo.Path,
		// Sure hope we don't have more than UINT_MAX repos someday
		ID: uint32(repo.ID),

		CommitURLTemplate:    fmt.Sprintf("%s/commit/{{.Version}}", baseURL),
		FileURLTemplate:      fmt.Sprintf("%s/tree/{{.Version}}/item/{{.Path}}", baseURL),
		LineFragmentTemplate: "#{{.LineNumber}}",

		Metadata: map[string]string{
			"rid":        repo.RID.String(),
			"owner":      ownerName,
			"visibility": repo.Visibility.String(),
		},

		RawConfig: map[string]string{
			"zoekt.web-url":      baseURL,
			"zoekt.web-url-type": "sourcehut",
			"zoekt.public":       public,
		},
	}

	gitopts := gitindex.Options{
		Submodules:   false,
		BuildOptions: opts,
		Incremental:  true,
		Branches:     []string{"HEAD"},
		RepoDir:      repo.Path,
	}

	if p, ok := conf.Get("git.sr.ht", "index-parallelism"); ok {
		opts.Parallelism, err = strconv.Atoi(p)
		if err != nil {
			panic(err)
		}
	}

	task := work.NewTask(func(ctx context.Context) error {
		_, err := gitindex.IndexGitRepo(gitopts)
		return err
	})

	sctx.queue.Enqueue(task)
	log.Printf("Enqueued search index refresh of repo %d", repo.ID)
}

// Deletes a repository from the search index
func Delete(ctx context.Context, repo *model.Repository) {
	sctx, ok := ctx.Value(ctxKey).(*SearchContext)
	if !ok {
		return
	}

	prefix := fmt.Sprintf("index_%010d_", repo.ID)
	task := work.NewTask(func(ctx context.Context) error {
		dir, err := os.Open(sctx.indexDir)
		if err != nil {
			return err
		}
		defer dir.Close()

		var files []string
		for {
			dents, err := dir.ReadDir(4096)
			if err == io.EOF {
				break
			} else if err != nil {
				return err
			}
			for _, dent := range dents {
				if !strings.HasPrefix(dent.Name(), prefix) {
					continue
				}
				files = append(files, path.Join(sctx.indexDir, dent.Name()))
			}
		}

		for _, file := range files {
			err := os.Remove(file)
			if err != nil {
				log.Printf("Warning: failed to remove %s: %s", file, err.Error())
			}
		}

		return err
	})

	sctx.queue.Enqueue(task)
	log.Printf("Enqueued search index purge of repo %d", repo.ID)
}
