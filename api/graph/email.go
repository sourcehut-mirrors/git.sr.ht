package graph

import (
	"context"
	"fmt"
	"strings"
	"text/template"

	"git.sr.ht/~sircmpwn/core-go/auth"
	"git.sr.ht/~sircmpwn/core-go/client"
	"git.sr.ht/~sircmpwn/core-go/config"
	"github.com/emersion/go-message/mail"
)

func sendEmail(ctx context.Context, address, message string) error {
	return client.Do(ctx, "", "meta.sr.ht", client.GraphQLQuery{
		Query: `
		mutation sendEmail($address: String!, $message: String!) {
			sendEmail(address: $address, message: $message)
		}`,
		Variables: map[string]any{
			"address": address,
			"message": message,
		},
	}, struct{}{})
}

func sendDeployKeyEvent(ctx context.Context, repo, event, fingerprint string) {
	owner := auth.ForContext(ctx)
	conf := config.ForContext(ctx)
	siteName, ok := conf.Get("sr.ht", "site-name")
	if !ok {
		panic(fmt.Errorf("expected [sr.ht]site-name in config"))
	}
	ownerName, ok := conf.Get("sr.ht", "owner-name")
	if !ok {
		panic(fmt.Errorf("expected [sr.ht]owner-name in config"))
	}

	address := mail.Address{
		Name:    owner.Username,
		Address: owner.Email,
	}
	type TemplateContext struct {
		OwnerName   string
		SiteName    string
		Username    string
		Event       string
		Fingerprint string
		RepoName    string
	}
	tctx := TemplateContext{
		OwnerName:   ownerName,
		SiteName:    siteName,
		Username:    owner.Username,
		Event:       event,
		Fingerprint: fingerprint,
		RepoName:    repo,
	}

	tmpl := template.Must(template.New("deploy-key-added").Parse(`Subject: SSH deploy key {{.Event}}

~{{.Username}},

This email was sent to inform you that the following security-sensitive 
event has occured on your {{.SiteName}} account:

SSH key {{.Fingerprint}} 
was {{.Event}} as a deploy key for your repository '{{.RepoName}}'.

If you did not expect this to occur, please reply to this email urgently 
to contact support. Otherwise, no action is required.
--
{{.OwnerName}}
{{.SiteName}}`))

	var message strings.Builder
	err := tmpl.Execute(&message, tctx)
	if err != nil {
		panic(err)
	}

	sendEmail(ctx, address.String(), message.String())
}
