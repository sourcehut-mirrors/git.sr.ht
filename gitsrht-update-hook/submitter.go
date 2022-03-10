package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"path"
	"strings"
	"unicode/utf8"

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

type BuildSubmitter interface {
	// Return a list of build manifests and their names
	FindManifests() (map[string]string, error)
	// Get builds.sr.ht origin
	GetBuildsOrigin() string
	// Get builds.sr.ht OAuth token
	GetOauthToken() *string
	// Get a checkout-able string to append to matching source URLs
	GetCommitId() string
	// Get the build note which corresponds to this commit
	GetCommitNote() string
	// Get the clone URL for this repository
	GetCloneUrl() string
	// Get the name of the repository
	GetRepoName() string
	// Get the name of the repository owner
	GetOwnerName() string
	// Get the job tags to use for this commit
	GetJobTags() []string
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
	pattern := ".build.yml,.builds/*.yml"
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

func (submitter GitBuildSubmitter) GetBuildsOrigin() string {
	return submitter.BuildOrigin
}

func (submitter GitBuildSubmitter) GetOauthToken() *string {
	return submitter.OwnerToken
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
	tags := []string{submitter.GetRepoName(), "commits"}
	if strings.HasPrefix(submitter.Ref, "refs/heads/") {
		tags = append(tags, strings.TrimPrefix(submitter.Ref, "refs/heads/"))
	}
	return tags
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

func (submitter GitBuildSubmitter) GetRepoName() string {
	return submitter.RepoName
}

func (submitter GitBuildSubmitter) GetOwnerName() string {
	return submitter.OwnerName
}

type BuildSubmission struct {
	// TODO: Move errors into this struct and set up per-submission error
	// tracking
	Name     string
	Response string
	Url      string
}

func configureRequestAuthorization(submitter BuildSubmitter,
	req *http.Request) {

	auth := InternalRequestAuthorization{
		ClientID: clientId,
		NodeID:   "git.sr.ht::update-hook",
		Username: submitter.GetOwnerName(),
	}
	authPayload, err := json.Marshal(&auth)
	if err != nil {
		logger.Fatalf("Failed to marshal internal authorization: %v", err)
	}
	enc, err := fernet.EncryptAndSign(authPayload, fernetKey)
	if err != nil {
		logger.Fatalf("Failed to encrypt internal authorization: %v", err)
	}
	req.Header.Add("X-Srht-Authorization", string(enc))
}

// TODO: Move this to scm.sr.ht
var submitBuildSkipCiPrinted bool

func SubmitBuild(submitter BuildSubmitter) ([]BuildSubmission, error) {
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

		client := &http.Client{}

		submission := struct {
			Manifest string   `json:"manifest"`
			Note     string   `json:"note"`
			Tags     []string `json:"tags"`
		}{
			Manifest: yaml,
			Tags:     append(submitter.GetJobTags(), name),
			Note:     submitter.GetCommitNote(),
		}
		bodyBytes, err := json.Marshal(&submission)
		if err != nil {
			return nil, errors.Wrap(err, "preparing job")
		}
		body := bytes.NewBuffer(bodyBytes)

		req, err := http.NewRequest("POST", fmt.Sprintf("%s/api/jobs",
			submitter.GetBuildsOrigin()), body)
		configureRequestAuthorization(submitter, req)
		req.Header.Add("Content-Type", "application/json")
		resp, err := client.Do(req)
		if err != nil {
			return nil, errors.Wrap(err, "job submission")
		}

		if resp.StatusCode == 403 {
			return nil, errors.New("builds.sr.ht returned 403\n" +
				"Log out and back into the website to authorize " +
				"builds integration.")
		}

		defer resp.Body.Close()
		respBytes, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			return nil, errors.Wrap(err, "read response")
		}

		if resp.StatusCode == 400 {
			return nil, errors.New(fmt.Sprintf(
				"builds.sr.ht returned %d\n", resp.StatusCode) +
				string(respBytes))
		}
		if resp.StatusCode == 402 {
			return nil, errors.New("Payment is required. Set up billing at https://meta.sr.ht/billing/initial")
		}

		var job struct {
			Id int `json:"id"`
		}
		err = json.Unmarshal(respBytes, &job)
		if err != nil {
			return nil, errors.Wrap(err, "interpret response")
		}

		results = append(results, BuildSubmission{
			Name: name,
			Url: fmt.Sprintf("%s/~%s/job/%d",
				submitter.GetBuildsOrigin(),
				submitter.GetOwnerName(),
				job.Id),
			Response: string(respBytes),
		})
	}

	return results, nil
}

func autoSetupManifest(submitter BuildSubmitter, manifest *Manifest) {
	var hasSelf bool
	cloneUrl := submitter.GetCloneUrl() + "#" + submitter.GetCommitId()
	for i, src := range manifest.Sources {
		if path.Base(src) == submitter.GetRepoName() {
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

	if manifest.Shell {
		manifest.Shell = false
		log.Println("Notice: removing 'shell: true' from build manifest")
	}
}
