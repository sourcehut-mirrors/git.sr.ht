package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"path"
	"strings"
	"unicode/utf8"

	"github.com/microcosm-cc/bluemonday"
	"github.com/pkg/errors"
	"gopkg.in/src-d/go-git.v4"
	"gopkg.in/src-d/go-git.v4/plumbing/object"
)

type BuildSubmitter interface {
	// Return a list of build manifests and their names
	FindManifests() (map[string]string, error)
	// Get builds.sr.ht origin
	GetBuildsOrigin() string
	// Get builds.sr.ht OAuth token
	GetOauthToken() string
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
	OwnerToken  string
	RepoName    string
	Repository  *git.Repository
	Visibility  string
}

func (submitter GitBuildSubmitter) FindManifests() (map[string]string, error) {
	tree, err := submitter.Repository.TreeObject(submitter.Commit.TreeHash)
	if err != nil {
		return nil, errors.Wrap(err, "lookup tree failed")
	}

	var files []*object.File
	file, err := tree.File(".build.yml")
	if err == nil {
		files = append(files, file)
	} else {
		subtree, err := tree.Tree(".builds")
		if err != nil {
			return nil, nil
		}
		entries := subtree.Files()
		for {
			file, err = entries.Next()
			if file == nil || err != nil {
				break
			}
			if strings.HasSuffix(file.Name, ".yml") {
				files = append(files, file)
			}
		}
		if err != io.EOF {
			return nil, errors.Wrap(err, "EOF finding build manifest")
		}
	}

	manifests := make(map[string]string)
	for _, file := range files {
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
		manifests[file.Name] = string(content)
	}
	return manifests, nil
}

func (submitter GitBuildSubmitter) GetBuildsOrigin() string {
	return submitter.BuildOrigin
}

func (submitter GitBuildSubmitter) GetOauthToken() string {
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

func (submitter GitBuildSubmitter) GetCommitNote() string {
	policy := bluemonday.StrictPolicy()
	commitUrl := fmt.Sprintf("%s/%s/%s/commit/%s", submitter.GitOrigin,
		submitter.OwnerName, submitter.RepoName,
		submitter.GetCommitId())
	return fmt.Sprintf(`[%s](%s) &mdash; [%s](mailto:%s)\n\n<pre>%s</pre>`,
		submitter.GetCommitId()[:7], commitUrl,
		submitter.Commit.Author.Name, submitter.Commit.Author.Email,
		policy.Sanitize(firstLine(submitter.Commit.Message)))
}

func (submitter GitBuildSubmitter) GetCloneUrl() string {
	if submitter.Visibility == "private" {
		origin := strings.ReplaceAll(submitter.GitOrigin, "http://", "")
		origin = strings.ReplaceAll(origin, "https://", "")
		// Use SSH URL
		return fmt.Sprintf("git+ssh://git@%s/~%s/%s", origin,
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
	Name string
	Url  string
}

// TODO: Move this to scm.sr.ht
func SubmitBuild(submitter BuildSubmitter) ([]BuildSubmission, error) {
	manifests, err := submitter.FindManifests()
	if err != nil || manifests == nil {
		return nil, err
	}

	var results []BuildSubmission
	for name, contents := range manifests {
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
			Tags     []string `json:"tags"`
		}{
			Manifest: yaml,
			Tags:     []string{submitter.GetRepoName(), name},
		}
		bodyBytes, err := json.Marshal(&submission)
		if err != nil {
			return nil, errors.Wrap(err, "preparing job")
		}
		body := bytes.NewBuffer(bodyBytes)

		req, err := http.NewRequest("POST", fmt.Sprintf("%s/api/jobs",
			submitter.GetBuildsOrigin()), body)
		req.Header.Add("Authorization", fmt.Sprintf("token %s",
			submitter.GetOauthToken()))
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
}
