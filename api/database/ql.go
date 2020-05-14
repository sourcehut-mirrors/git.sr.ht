package database

import (
	"context"
	"sort"

	"github.com/lib/pq"
	"github.com/vektah/gqlparser/v2/ast"

	"github.com/99designs/gqlgen/graphql"
)

func collectFields(ctx context.Context) []graphql.CollectedField {
	var fields []graphql.CollectedField
	if graphql.GetFieldContext(ctx) != nil {
		fields = graphql.CollectFieldsCtx(ctx, nil)

		octx := graphql.GetOperationContext(ctx)
		for _, col := range fields {
			if col.Name == "results" {
				// This endpoint is using the cursor pattern; the columns we
				// actually need to filter with are nested into the results
				// field.
				fields = graphql.CollectFields(octx, col.SelectionSet, nil)
				break
			}
		}
	}
	return fields
}

func ColumnsFor(ctx context.Context, alias string,
	colMap map[string]string) []string {

	fields := collectFields(ctx)
	if len(fields) == 0 {
		// Collect all fields if we are not in an active graphql context
		for qlCol, _ := range colMap {
			fields = append(fields, graphql.CollectedField{
				&ast.Field{Name: qlCol}, nil,
			})
		}
	}

	sort.Slice(fields, func(a, b int) bool {
		return fields[a].Name < fields[b].Name
	})

	var columns []string
	for _, qlCol := range fields {
		if sqlCol, ok := colMap[qlCol.Name]; ok {
			if alias != "" {
				columns = append(columns, pq.QuoteIdentifier(alias)+
					"."+pq.QuoteIdentifier(sqlCol))
			} else {
				columns = append(columns, pq.QuoteIdentifier(sqlCol))
			}
		}
	}

	return columns
}

func FieldsFor(ctx context.Context,
	colMap map[string]interface{}) []interface{} {

	qlFields := collectFields(ctx)
	if len(qlFields) == 0 {
		// Collect all fields if we are not in an active graphql context
		for qlCol, _ := range colMap {
			qlFields = append(qlFields, graphql.CollectedField{
				&ast.Field{Name: qlCol}, nil,
			})
		}
	}

	sort.Slice(qlFields, func(a, b int) bool {
		return qlFields[a].Name < qlFields[b].Name
	})

	var fields []interface{}
	for _, qlField := range qlFields {
		if field, ok := colMap[qlField.Name]; ok {
			fields = append(fields, field)
		}
	}

	return fields
}

func WithAlias(alias, col string) string {
	if alias != "" {
		return alias + "." + col
	} else {
		return col
	}
}
