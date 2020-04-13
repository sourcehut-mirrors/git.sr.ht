package model

import (
	"context"
	"sort"

	"git.sr.ht/~sircmpwn/gqlgen/graphql"
	"github.com/vektah/gqlparser/v2/ast"
)

func ColumnsFor(ctx context.Context,
	colMap map[string]string, tbl string) []string {

	var fields []graphql.CollectedField
	if graphql.GetFieldContext(ctx) != nil {
		fields = graphql.CollectFieldsCtx(ctx, nil)
	} else {
		// Collect all fields if we are not in an active graphql context
		for qlCol, _ := range colMap {
			fields = append(fields, graphql.CollectedField{
				&ast.Field{Name: qlCol}, nil,
			})
		}
	}

	sort.Slice(fields, func (a, b int) bool {
		return fields[a].Name < fields[b].Name
	})

	var columns []string
	for _, qlCol := range fields {
		if sqlCol, ok := colMap[qlCol.Name]; ok {
			columns = append(columns, tbl + "." + sqlCol)
		}
	}

	return columns
}

func FieldsFor(ctx context.Context,
	colMap map[string]interface{}) []interface{} {

	var qlFields []graphql.CollectedField
	if graphql.GetFieldContext(ctx) != nil {
		qlFields = graphql.CollectFieldsCtx(ctx, nil)
	} else {
		// Collect all fields if we are not in an active graphql context
		for qlCol, _ := range colMap {
			qlFields = append(qlFields, graphql.CollectedField{
				&ast.Field{Name: qlCol}, nil,
			})
		}
	}

	sort.Slice(qlFields, func (a, b int) bool {
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
