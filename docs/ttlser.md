# Specification for the serialization produced by ttlser.py

## High level formatting
1. A single newline `\n` occurs after all lines.
2. A second newline shall occur only in the following cases.
    1. After the last line of the prefix section.
    2. After every section header.
    3. After the closing line (the one with a period `.`) of a `rdf:type` block.
3. Indentation.
	1. There shall be no indentation for `@prefix` lines.
	2. There shall be no indentation for lines representing top level triples (e.g. `rdf:type` lines).
	3. There shall be no indentation for section header lines.
	4. Lines representing triples with lower priority predicates (e.g. `rdfs:subClassOf`) shall have one additional indentation block of 4 spaces preceeding them in addition to the number of indentation blocks preceeding the line for the highest priority triple with which they share their subject. For example a `rdfs:subClassOf` triple line sharing a subject with a top level `owl:Class` triple line should have exactly 1 indentation block of 4 spaces preceeding the `r` in `rdfs:subClassOf`.
	5. Elements of an `rdf:List` shall all have only 1 additional indentation block beyond that of a normal object.
4. All opening parenthesis shall occur on the same line is the subject they represent.
5. All closing parenthesis and brackets shall occur on the same line, each separated by a single space (lisp style).
6. Opening parenthesis of an `rdf:List` shall be follow by a newline.
7. Opening brackets shall NOT be followed by a newline.
8. There shall be 1 space between subject, predicate, object, parenthesis, square brackets, `;`, and `.`.
9. There shall be NO space preceding a comma `,` separating a list of predicate-objects sharing the same subject.

## Alphabetical ordering
Alphabetical ordering in this document means the following.
* Orderings are defined over a set of string representations of the qname forms of subjects, predicates, or objects. Anonymous BNodes should be considered to be null thus should not be considered when sorting alphabetically.
* Values that do not have a qname representation (e.g. `<http://example.org>` or `"Hello world"`) and that are not BNodes shall be taken as is.
* The ordering shall be a natural sort (such that `'a9'` comes before `'a10'` and `'a11111111'`) with an exception describe in the next point.
* The ordering shall put `'a'` after `'A'` but before `'B'`. Essentially this can be interpreted to mean that capital vs lowercase should be ignored when ordering between different letters (e.g. `A` vs `B` or `c` vs `D`) but should be taken into account when breaking ties where there are two identical strings that differ only in their capitalization. This means that `'bb'` comes before `'Bbb'`.


## Ordering rules
1. Class orderings and predicate orderings are as listed at the start of `CustomTurtleSerializer`. In theory these orderings could be maintained in a separate file that any conforming serializer could import.
2. Likewise section headers are as specified in the `SECTIONS` portion of `CustomTurtleSerializer`.
3. `@prefix` lines shall be ordered alphabetically by `(prefix, namespace)` pairs. For example `@prefix a: <http://a.org>` will precede `@prefix A: <http://AA.org>`. Another way to get the same ordering as using prefix namespace pairs is to sort the set of whole prefix lines alphabetically.
4. Within a section (demarcated by a header) the ordering of entries shall first be in order of their top level class and then alphabetically.
5. Orderings of the contents of `rdf:List`s shall be alphabetical.
6. Orderings of `owl:Restriction`s shall be alphabetically first by the object of their `owl:onProperty` statement, then alphabetically by `owl:allValuesFrom` vs `owl:someValuesFrom`, then alphabetically by the `*ValuesFrom` object.
7. Orderings of literals shall be alphabetical the triple `(value, datatype, language)` with the empty string `''` being substituted for either datatype or language either is missing.

## Implementation note
This is currently implemented in [ttlser.py](../pyontutils/ttlser.py) by finding a total ordering on all URIs and Literals, and then using the ranks on those nodes to calculate ranks for any BNode that is their parent. This provides a global total ordering for all triples than can then be used to produce deterministic output recursively.
