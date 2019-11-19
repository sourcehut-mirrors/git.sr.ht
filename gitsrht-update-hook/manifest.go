package main

// TODO: Move this into builds.sr.ht

import (
	"gopkg.in/yaml.v2"
)

type Manifest struct {
	Arch         *string                  `yaml:"arch",omitempty`
	Environment  map[string]interface{}   `yaml:"environment",omitempty`
	Image        string                   `yaml:"image"`
	Packages     []string                 `yaml:"packages",omitempty`
	Repositories map[string]string        `yaml:"repositories",omitempty`
	Secrets      []string                 `yaml:"secrets",omitempty`
	Shell        bool                     `yaml:"shell",omitempty`
	Sources      []string                 `yaml:"sources",omitempty`
	Tasks        []map[string]string      `yaml:"tasks"`
	Triggers     []map[string]interface{} `yaml:"triggers",omitempty`
}

func ManifestFromYAML(src string) (Manifest, error) {
	var m Manifest
	if err := yaml.Unmarshal([]byte(src), &m); err != nil {
		return m, err
	}
	// XXX: We could do validation here, but builds.sr.ht will also catch it
	// for us later so it's not especially important to
	return m, nil
}

func (manifest Manifest) ToYAML() (string, error) {
	bytes, err := yaml.Marshal(&manifest)
	if err != nil {
		return "", err
	}
	return string(bytes), nil
}
