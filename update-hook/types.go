package main

type RepoContext struct {
	Id           int    `json:"id"`
	Name         string `json:"name"`
	OwnerId      int    `json:"owner_id"`
	OwnerName    string `json:"owner_name"`
	Path         string `json:"path"`
	AbsolutePath string `json:"absolute_path"`
	Visibility   string `json:"visibility"`
	Autocreated  bool   `json:"autocreated"`
}

type UserContext struct {
	CanonicalName string `json:"canonical_name"`
	Name          string `json:"name"`
}

type PushContext struct {
	Repo RepoContext `json:"repo"`
	User UserContext `json:"user"`
}
