// Command rename_entry is the grader's: it finds the one package-level declaration of
// WriteSummary in the Go files it is given (those `go list` selects for the package, so a file
// that the build rules leave out is never read) and prints its file and the byte offset of its
// name, so the grader can rename it and wrap it. The declaration is a function, or a variable
// that holds one. It exits 2 where there is no such declaration or more than one, and 1 where a
// file does not parse.
package main

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"sort"
)

const entry = "WriteSummary"

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: rename_entry FILE...")
		os.Exit(2)
	}
	files := append([]string(nil), os.Args[1:]...)
	sort.Strings(files)
	fset := token.NewFileSet()
	var found []string
	for _, path := range files {
		file, err := parser.ParseFile(fset, path, nil, parser.SkipObjectResolution)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		for _, decl := range file.Decls {
			for _, name := range names(decl) {
				if name.Name == entry {
					found = append(found, fmt.Sprintf("%s\t%d", path, fset.Position(name.Pos()).Offset))
				}
			}
		}
	}
	if len(found) != 1 {
		fmt.Fprintf(os.Stderr, "%d package-level declarations of %s\n", len(found), entry)
		os.Exit(2)
	}
	fmt.Println(found[0])
}

// names are the identifiers a package-level declaration declares: a function's name (not a
// method's), and each name of a variable or constant specification.
func names(decl ast.Decl) []*ast.Ident {
	switch d := decl.(type) {
	case *ast.FuncDecl:
		if d.Recv == nil {
			return []*ast.Ident{d.Name}
		}
	case *ast.GenDecl:
		var found []*ast.Ident
		for _, spec := range d.Specs {
			if value, ok := spec.(*ast.ValueSpec); ok {
				found = append(found, value.Names...)
			}
		}
		return found
	}
	return nil
}
