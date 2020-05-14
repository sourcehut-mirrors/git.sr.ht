package auth

import (
	"context"
	"crypto/sha512"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/vektah/gqlparser/gqlerror"

	"git.sr.ht/~sircmpwn/git.sr.ht/api/crypto"
	"git.sr.ht/~sircmpwn/git.sr.ht/api/database"
)

var userCtxKey = &contextKey{"user"}

type contextKey struct {
	name string
}

var bearerRegex = regexp.MustCompile(`^[0-9a-f]{32}$`)

const (
	USER_UNCONFIRMED       = "unconfirmed"
	USER_ACTIVE_NON_PAYING = "active_non_paying"
	USER_ACTIVE_FREE       = "active_free"
	USER_ACTIVE_PAYING     = "active_paying"
	USER_ACTIVE_DELINQUENT = "active_delinquent"
	USER_ADMIN             = "admin"
	USER_UNKNOWN           = "unknown"
	USER_SUSPENDED         = "suspended"
)

type User struct {
	ID               int
	Created          time.Time
	Updated          time.Time
	Username         string
	Email            string
	UserType         string
	URL              *string
	Location         *string
	Bio              *string
	SuspensionNotice *string
}

func authError(w http.ResponseWriter, reason string, code int) {
	gqlerr := gqlerror.Errorf("Authentication error: %s", reason)
	b, err := json.Marshal(gqlerr)
	if err != nil {
		panic(err)
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	w.Write(b)
}

type AuthCookie struct {
	Name string `json:"name"`
}

func cookieAuth(db *sql.DB, cookie *http.Cookie,
	w http.ResponseWriter, r *http.Request, next http.Handler) {

	payload := crypto.Decrypt([]byte(cookie.Value))
	if payload == nil {
		authError(w, "Invalid authentication cookie", http.StatusForbidden)
		return
	}

	var (
		auth AuthCookie
		err  error
		rows *sql.Rows
		user User
	)
	if err := json.Unmarshal(payload, &auth); err != nil {
		authError(w, "Invalid authentication cookie", http.StatusForbidden)
		return
	}

	query := database.
		Select(context.TODO(), []string{
			`u.id`, `u.username`,
			`u.created`, `u.updated`,
			`u.email`,
			`u.user_type`,
			`u.url`, `u.location`, `u.bio`,
			`u.suspension_notice`,
		}).
		From(`"user" u`).
		Where(`u.username = ?`, auth.Name)
	if rows, err = query.RunWith(db).Query(); err != nil {
		panic(err)
	}
	defer rows.Close()

	if !rows.Next() {
		if err := rows.Err(); err != nil {
			panic(err)
		}
		authError(w, "Invalid or expired OAuth token", http.StatusForbidden)
		return
	}
	if err := rows.Scan(&user.ID, &user.Username, &user.Created, &user.Updated,
		&user.Email, &user.UserType, &user.URL, &user.Location, &user.Bio,
		&user.SuspensionNotice); err != nil {
		panic(err)
	}
	if rows.Next() {
		if err := rows.Err(); err != nil {
			panic(err)
		}
		panic(errors.New("Multiple matching user accounts; invariant broken"))
	}

	if user.UserType == USER_SUSPENDED {
		authError(w, fmt.Sprintf("Account suspended with the following notice: %s\nContact support",
			user.SuspensionNotice), http.StatusForbidden)
		return
	}

	ctx := context.WithValue(r.Context(), userCtxKey, &user)

	r = r.WithContext(ctx)
	next.ServeHTTP(w, r)
}

func Middleware(db *sql.DB) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.URL.Path != "/query" {
				next.ServeHTTP(w, r)
				return
			}

			cookie, err := r.Cookie("sr.ht.unified-login.v1")
			if err == nil {
				cookieAuth(db, cookie, w, r, next)
				return
			}

			auth := r.Header.Get("Authorization")
			if auth == "" {
				authError(w, `Authorization header is required.
Expected 'Authorization: Bearer <token>'`, http.StatusForbidden)
				return
			}

			z := strings.SplitN(auth, " ", 2)
			if len(z) != 2 {
				authError(w, "Invalid Authorization header", http.StatusBadRequest)
				return
			}

			var bearer string
			switch z[0] {
			case "Bearer":
				token := []byte(z[1])
				if !bearerRegex.Match(token) {
					authError(w, "Invalid bearer token, expected 32-character haxadecimal string", http.StatusBadRequest)
					return
				}
				hash := sha512.Sum512(token)
				bearer = hex.EncodeToString(hash[:])
			case "Internal":
				panic(errors.New("TODO"))
			default:
				authError(w, "Invalid Authorization header", http.StatusBadRequest)
				return
			}

			var (
				expires time.Time
				rows    *sql.Rows
				scopes  string
				user    User
			)
			query := database.
				Select(context.TODO(), []string{
					`ot.expires`,
					`ot.scopes`,
					`u.id`, `u.username`,
					`u.created`, `u.updated`,
					`u.email`,
					`u.user_type`,
					`u.url`, `u.location`, `u.bio`,
					`u.suspension_notice`,
				}).
				From(`oauthtoken ot`).
				Join(`"user" u ON u.id = ot.user_id`).
				Where(`ot.token_hash = ?`, bearer)
			if rows, err = query.RunWith(db).Query(); err != nil {
				panic(err)
			}
			defer rows.Close()

			if !rows.Next() {
				if err := rows.Err(); err != nil {
					panic(err)
				}
				authError(w, "Invalid or expired OAuth token", http.StatusForbidden)
				return
			}
			if err := rows.Scan(&expires, &scopes,
				&user.ID, &user.Username,
				&user.Created, &user.Updated,
				&user.Email,
				&user.UserType,
				&user.URL,
				&user.Location,
				&user.Bio,
				&user.SuspensionNotice); err != nil {
				panic(err)
			}
			if rows.Next() {
				if err := rows.Err(); err != nil {
					panic(err)
				}
				panic(errors.New("Multiple matching OAuth tokens; invariant broken"))
			}

			if time.Now().UTC().After(expires) {
				authError(w, "Invalid or expired OAuth token", http.StatusForbidden)
				return
			}

			if user.UserType == USER_SUSPENDED {
				authError(w, fmt.Sprintf("Account suspended with the following notice: %s\nContact support",
					user.SuspensionNotice), http.StatusForbidden)
				return
			}

			if scopes != "*" && scopes != "*:read" && scopes != "*:write" {
				authError(w, "Presently, OAuth authentication to the GraphQL API is only supported for OAuth tokens with all permissions, namely '*'.", http.StatusForbidden)
				return
			}

			ctx := context.WithValue(r.Context(), userCtxKey, &user)

			r = r.WithContext(ctx)
			next.ServeHTTP(w, r)
		})
	}
}

func ForContext(ctx context.Context) *User {
	raw, ok := ctx.Value(userCtxKey).(*User)
	if !ok {
		panic(errors.New("Invalid authentication context"))
	}
	return raw
}
