package main

import (
	"bufio"
	"bytes"
	"context"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"path"
	"strings"
	"unicode/utf8"

	"git.sr.ht/~sircmpwn/core-go/client"
	"git.sr.ht/~turminal/go-fnmatch"
	"github.com/fernet/fernet-go"
	"github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/plumbing"
	"github.com/go-git/go-git/v5/plumbing/filemode"
	"github.com/go-git/go-git/v5/plumbing/object"
	"github.com/pkg/errors"
)

var (
	fernetKey *fernet.Key
	clientId  string
)

// TODO: Consider moving Fernet code to a shared SourceHut Go module
func initSubmitter() {
	netkey, ok := config.Get("sr.ht", "network-key")
	if !ok {
		logger.Fatal("Configuration error: [sr.ht].network-key missing")
	}
	var err error
	fernetKey, err = fernet.DecodeKey(netkey)
	if err != nil {
		logger.Fatalf("Error decoding [sr.ht].network-key: %v", err)
	}
	clientId, ok = config.Get("git.sr.ht", "oauth-client-id")
	if !ok {
		logger.Fatal("Configuration error: [git.sr.ht].oauth-client-id missing")
	}
}

type InternalRequestAuthorization struct {
	ClientID string `json:"client_id"`
	NodeID   string `json:"node_id"`
	Username string `json:"name"`
}

// SQL notes
//
// We need:
// - The repo ID
// - The repo name & visibility
// - The owner's username & canonical name
// - The owner's OAuth token & scopes
// - A list of affected webhooks
type GitBuildSubmitter struct {
	BuildOrigin string
	Commit      *object.Commit
	GitOrigin   string
	OwnerName   string
	OwnerToken  *string
	PusherName  string
	RepoName    string
	Repository  *git.Repository
	Visibility  string
	Ref         string
}

func (submitter GitBuildSubmitter) FindManifests() (map[string]string, error) {
	rootTree, err := submitter.Repository.TreeObject(submitter.Commit.TreeHash)
	if err != nil {
		return nil, errors.Wrap(err, "root tree lookup failed")
	}

	var files []*object.File
	loadOptions()
	pattern := ".build.yml,.builds/*.yml,.build.yaml,.builds/*.yaml"
	if pat, ok := options["submit"]; ok {
		pattern = pat
	}
	for _, pat := range strings.Split(pattern, ",") {
		// If exact match: get to the blob directly
		// Otherwise:      find the longest prefix and start walking from there

		asterisk := strings.Index(pat, "*")
		isWildcard := asterisk != -1
		if !isWildcard {
			file, err := rootTree.File(pat)
			if err != nil && err != object.ErrFileNotFound {
				return nil, errors.Wrap(err, "getting file")
			}
			if file != nil {
				files = append(files, file)
			}
		} else {
			var tree *object.Tree
			var prefix string
			for strings.HasPrefix(pat, "/") {
				pat = pat[1:]
			}
			if pref := strings.LastIndex(pat, "/"); pref != -1 {
				tree, err = rootTree.Tree(pat[:pref])
				if err != nil && err != object.ErrDirectoryNotFound {
					return nil, errors.Wrap(err, "getting pref tree")
				}
				prefix = pat[:pref+1]
				pat = pat[pref+1:]
			} else {
				tree = rootTree
			}
			if tree == nil {
				continue
			}

			traversal := object.NewTreeWalker(tree, true, make(map[plumbing.Hash]bool))
			defer traversal.Close()
			for {
				name, entry, err := traversal.Next()
				if err == io.EOF {
					break
				} else if err != nil {
					return nil, errors.Wrap(err, "iterating worktree")
				}

				if fnmatch.Match(pat, name, fnmatch.FNM_PATHNAME) {
					if entry.Mode == filemode.Dir || entry.Mode == filemode.Submodule {
						continue // Match iteration behaviour of subtree.Files()
					}

					file, err := tree.TreeEntryFile(&entry)
					if file == nil || err != nil {
						return nil, errors.Wrap(err, "getting file for entry")
					}

					file.Name = prefix + file.Name
					files = append(files, file)
				}
			}
		}
	}

	manifests := make(map[string]string)
	for _, file := range files {
		basename := path.Base(file.Name)
		if _, ok := manifests[basename]; ok {
			log.Printf("Not submitting duplicate manifest %s [%s]\n", file.Name, basename)
			continue
		}

		var (
			reader  io.Reader
			content []byte
		)
		if reader, err = file.Reader(); err != nil {
			return nil, errors.Wrapf(err, "creating reader for %s", file.Name)
		}
		if content, err = ioutil.ReadAll(reader); err != nil {
			return nil, errors.Wrap(err, "reading build manifest")
		}
		if !utf8.Valid(content) {
			return nil, errors.Wrap(err, "manifest is not valid UTF-8 file")
		}
		manifests[basename] = string(content)
	}
	return manifests, nil
}

func (submitter GitBuildSubmitter) GetCommitId() string {
	return submitter.Commit.Hash.String()
}

func firstLine(text string) string {
	buf := bytes.NewBufferString(text)
	scanner := bufio.NewScanner(buf)
	if !scanner.Scan() {
		return ""
	}
	return scanner.Text()
}

// via https://github.com/openconfig/goyang, Apache 2.0
func indent(indent, s string) string {
	if indent == "" || s == "" {
		return s
	}
	lines := strings.SplitAfter(s, "\n")
	if len(lines[len(lines)-1]) == 0 {
		lines = lines[:len(lines)-1]
	}
	return strings.Join(append([]string{""}, lines...), indent)
}

func (submitter GitBuildSubmitter) GetCommitNote() string {
	commitUrl := fmt.Sprintf("%s/~%s/%s/commit/%s", submitter.GitOrigin,
		submitter.OwnerName, submitter.RepoName,
		submitter.GetCommitId())
	return fmt.Sprintf("[%s][0] — [%s][1]\n\n%s\n\n[0]: %s\n[1]: mailto:%s",
		submitter.GetCommitId()[:7],
		submitter.Commit.Author.Name,
		indent("    ", firstLine(submitter.Commit.Message)),
		commitUrl, submitter.Commit.Author.Email)
}

func (submitter GitBuildSubmitter) GetJobTags() []string {
	tags := []string{submitter.RepoName, "commits"}
	if strings.HasPrefix(submitter.Ref, "refs/heads/") {
		tags = append(tags, strings.TrimPrefix(submitter.Ref, "refs/heads/"))
	}
	return tags
}

func (submitter GitBuildSubmitter) GetEnv() map[string]string {
	return map[string]string{
		"GIT_REF": submitter.Ref,
	}
}

func (submitter GitBuildSubmitter) GetCloneUrl() string {
	if submitter.Visibility == "PRIVATE" {
		origin := strings.ReplaceAll(submitter.GitOrigin, "http://", "")
		origin = strings.ReplaceAll(origin, "https://", "")
		// Use SSH URL
		git_user, ok := config.Get("git.sr.ht::dispatch", "/usr/bin/gitsrht-keys")
		if !ok {
			git_user = "git:git"
		}
		git_user = strings.Split(git_user, ":")[0]
		return fmt.Sprintf("git+ssh://%s@%s/~%s/%s", git_user, origin,
			submitter.OwnerName, submitter.RepoName)
	} else {
		// Use HTTP(s) URL
		return fmt.Sprintf("%s/~%s/%s", submitter.GitOrigin,
			submitter.OwnerName, submitter.RepoName)
	}
}

type BuildSubmission struct {
	// TODO: Move errors into this struct and set up per-submission error
	// tracking
	Name string
	Url  string
}

// TODO: Move this to scm.sr.ht
var submitBuildSkipCiPrinted bool

func SubmitBuild(ctx context.Context, submitter *GitBuildSubmitter) ([]BuildSubmission, error) {
	manifests, err := submitter.FindManifests()
	if err != nil || manifests == nil {
		return nil, err
	}

	loadOptions()
	if _, ok := options["skip-ci"]; ok {
		if !submitBuildSkipCiPrinted {
			log.Println("skip-ci was requested - not submitting build jobs")
			submitBuildSkipCiPrinted = true
		}
		return nil, nil
	}

	var results []BuildSubmission
	for name, contents := range manifests {
		if len(results) >= 4 {
			log.Println("Notice: refusing to submit >4 builds")
			break
		}

		manifest, err := ManifestFromYAML(contents)
		if err != nil {
			return nil, errors.Wrap(err, name)
		}
		autoSetupManifest(submitter, &manifest)

		yaml, err := manifest.ToYAML()
		if err != nil {
			return nil, errors.Wrap(err, name)
		}

		query := client.GraphQLQuery{
			Query: `
			mutation SubmitBuild(
				$manifest: String!,
				$note: String,
				$tags: [String!],
				$secrets: Boolean,
				$visibility: Visibility,
			) {
				submit(
					manifest: $manifest,
					note: $note,
					tags: $tags,
					secrets: $secrets,
					visibility: $visibility,
				) {
					id
				}
			}`,
			Variables: map[string]interface{}{
				"manifest":   yaml,
				"tags":       append(submitter.GetJobTags(), name),
				"note":       submitter.GetCommitNote(),
				"visibility": submitter.Visibility,
				"secrets":    true,
			},
		}

		var resp struct {
			Submit struct {
				ID int `json:"id"`
			} `json:"submit"`
		}

		err = client.Do(ctx, submitter.PusherName, "builds.sr.ht", query, &resp)
		if err != nil {
			logger.Printf("Error submitting build: %v", err)
			return nil, err
		}

		results = append(results, BuildSubmission{
			Name: name,
			Url: fmt.Sprintf("%s/~%s/job/%d",
				submitter.BuildOrigin,
				submitter.PusherName,
				resp.Submit.ID),
		})
	}

	return results, nil
}

func autoSetupManifest(submitter *GitBuildSubmitter, manifest *Manifest) {
	var hasSelf bool
	cloneUrl := submitter.GetCloneUrl() + "#" + submitter.GetCommitId()
	for i, src := range manifest.Sources {
		if path.Base(src) == submitter.RepoName {
			manifest.Sources[i] = cloneUrl
			hasSelf = true
		}
	}
	if !hasSelf {
		manifest.Sources = append(manifest.Sources, cloneUrl)
	}

	if manifest.Environment == nil {
		manifest.Environment = make(map[string]interface{})
	}
	manifest.Environment["BUILD_SUBMITTER"] = "git.sr.ht"
	for k, v := range submitter.GetEnv() {
		manifest.Environment[k] = v
	}

	if manifest.Shell {
		manifest.Shell = false
		log.Println("Notice: removing 'shell: true' from build manifest")
	}
}
