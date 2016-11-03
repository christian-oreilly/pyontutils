#!/usr/bin/env python3.5
import re
from rdflib.plugins.serializers.turtle import TurtleSerializer
from rdflib import RDF, RDFS, OWL, BNode, URIRef
from rdflib.namespace import SKOS, DC, Namespace
from IPython import embed

OBOANN = Namespace('http://ontology.neuinfo.org/NIF/Backend/OBO_annotation_properties.owl#')
BIRNANN = Namespace('http://ontology.neuinfo.org/NIF/Backend/BIRNLex_annotation_properties.owl#')
oboInOwl = Namespace('http://www.geneontology.org/formats/oboInOwl#')
#IAO = Namespace('http://purl.obolibrary.org/obo/IAO_')  # won't work because numbers ...

def natsort(s, pat=re.compile(r'([0-9]+)')):
    return [int(t) if t.isdigit() else t.lower() for t in pat.split(s)]


# desired behavior
# 1) if there is more than one entry at a level URIRef goes first natsorted then lists then predicate lists then subject lists
# 2) sorting for nested structures in a list determined by
#     a) rank of object attached to the highest ranked predicate (could just be alpha)
#     b) rank of object attached to the second highest ranked predicate
#     c) where there are multiple of the same predicate their own rank is determined by the ranks of their objects
#     d) predicate lists are ranked -2 and subject (proper?) lists are ranked -1 as predicates
#     e) sorting proper lists... get the predicate rank and then the rank of the value
# object type ranks:
#  1 URIRef
#  2 predicate list []
#  3 proper list ()
# object value ranks:
#  1 URIRef -> alphabetical
#  2 lists -> object type ranks of their nth elements
#
# a nice example is NIF-Cell:nlx_cell_091210 in NIF-Neuron-BrainRegion-Bridge.ttl

SUBJECT = 0
VERB = 1
OBJECT = 2

class CustomTurtleSerializer(TurtleSerializer):
    """ NIFSTD custom ttl serliziation """

    topClasses = [RDFS.Class,
                  OWL.Ontology,
                  OWL.ObjectProperty,
                  OWL.AnnotationProperty,
                  OWL.Class,
                 ]

    predicateOrder = [RDF.type,
                      OWL.onProperty,
                      OWL.allValuesFrom,
                      OWL.someValuesFrom,
                      OWL.imports,
                      OWL.deprecated,
                      URIRef('http://purl.obolibrary.org/obo/IAO_0100001'),  # replacedBy:
                      oboInOwl.hasDbXref,
                      OWL.equivalentClass,
                      RDFS.label,
                      SKOS.prefLabel,
                      OBOANN.synonym,
                      OBOANN.abbrev,
                      DC.title,
                      SKOS.definition,
                      DC.description,
                      RDFS.subClassOf,
                      OWL.intersectionOf,
                      OWL.unionOf,
                      OWL.disjointWith,
                      OWL.disjointUnionOf,
                      RDFS.comment,
                      SKOS.note,
                      SKOS.editorialNote,
                      SKOS.changeNote,
                      OWL.versionInfo,
                      OBOANN.createdDate,
                      OBOANN.modifiedDate,
                     ]

    def __init__(self, store):  # for some reason this produces weird prefix errors!?
        super(CustomTurtleSerializer, self).__init__(store)
        self._local_order = []  # for tracking non BNode sort values
        self.object_rank = {o:i  # global rank for all URIRef that appear as objects
                            for i, o in
                            enumerate(
                                sorted(set([_ for _ in self.store.objects(None, None)
                                        if isinstance(_, URIRef)] +
                                           [_ for _ in self.store.subjects(None, None)
                                        if isinstance(_, URIRef)]),
                                       key=lambda _: natsort(self.store.qname(_))))}

        self.node_rank = {}
        def recurse(node, rank):  # XXX warning: cycles?
            for s in self.store.subjects(None, node):
                if isinstance(s, BNode):
                    if s not in self.node_rank:
                        self.node_rank[s] = rank
                    else:
                        self.node_rank[s] += rank
                    recurse(s, rank)  # if we are retracing steps we already added previous ranks to upstream so don't need to propagate again

        for o, r in self.object_rank.items():
            recurse(o, r)

        #embed()

    def _bnKey(self, bnode):
        if isinstance(bnode, BNode):
            return self.node_rank[bnode]
        elif isinstance(bnode, URIRef):
            return self.object_rank[bnode]
        #return sum([ord(_) / 26 * (i + 1) for i, _ in enumerate(bnode)])
        return 0  # we have previously sorted so alpha should be stable?

    def startDocument(self):
        self._started = True
        ns_list = sorted(self.namespaces.items(), key=lambda kv: (natsort(kv[0]), kv[1]))
        for prefix, uri in ns_list:
            self.write(self.indent() + '@prefix %s: <%s> .\n' % (prefix, uri))
        if ns_list and self._spacious:
            self.write('\n')

    def orderSubjects(self):  # copied over to enable natural sort of subjects
        seen = {}
        subjects = []

        def key(m):
            if not isinstance(m, BNode):
                m = self.store.qname(m)
            return natsort(m)

        for classURI in self.topClasses:
            members = list(self.store.subjects(RDF.type, classURI))
            members.sort(key=key)

            for member in members:
                subjects.append(member)
                self._topLevels[member] = True
                seen[member] = True

        recursable = [
            (isinstance(subject, BNode),
             self._references[subject], subject)
            for subject in self._subjects if subject not in seen]

        recursable.sort(key=lambda t: self._bnKey(t[-1]))

        #recursable.sort(key=lambda r: natsort(r[-1]))
        subjects.extend([subject for (isbnode, refs, subject) in recursable])

        return subjects

    def predicateList(self, subject, newline=False):
        properties = self.buildPredicateHash(subject)
        propList = self.sortProperties(properties)
        if len(propList) == 0:
            return
        self.verb(propList[0], newline=newline)
        self.objectList(properties[propList[0]])
        for predicate in propList[1:]:
            self.write(' ;\n' + self.indent(1))
            self.verb(predicate, newline=True)
            #self.objectList(sorted(properties[predicate], key=natsort))
            self.objectList(properties[predicate])

    def sortProperties(self, properties):
        """Take a hash from predicate uris to lists of values.
           Sort the lists of values.  Return a sorted list of properties."""
        # Sort object lists
        for prop, objects in properties.items():
            #objects.sort(key=natsort)
            objects.sort()
            objects.sort(key=self._bnKey)

        # Make sorted list of properties
        propList = []
        seen = {}
        for prop in self.predicateOrder:
            if (prop in properties) and (prop not in seen):
                propList.append(prop)
                seen[prop] = True
        props = list(properties.keys())
        props.sort(key=natsort)
        for prop in props:
            if prop not in seen:
                propList.append(prop)
                seen[prop] = True
        return propList

    def buildPredicateHash(self, subject):
        """
        Build a hash key by predicate to a list of objects for the given
        subject
        """
        properties = {}
        for s, p, o in self.store.triples((subject, None, None)):
            oList = properties.get(p, [])
            oList.append(o)
            properties[p] = oList

        #for k in properties:
            #properties[k].sort(key=natsort)

        #print(properties)

        return properties

    def doList(self, l):
        while l:
            item = self.store.value(l, RDF.first)
            if item is not None:
                self.write('\n' + self.indent(1))
                self.path(item, OBJECT, newline=True)
                self.subjectDone(l)
            l = self.store.value(l, RDF.rest)

    def p_default(self, node, position, newline=False):
        if position != SUBJECT and not newline:
            self.write(' ')
        self.write(self.label(node, position))
        return True

    def p_squared(self, node, position, newline=False):
        if (not isinstance(node, BNode)
                or node in self._serialized
                or self._references[node] > 1
                or position == SUBJECT):
            return False

        if not newline:
            self.write(' ')

        if self.isValidList(node):
            # this is a list
            self.write('(')
            self.depth += 1  # 2
            self.doList(node)
            self.depth -= 1  # 2
            self.write(' )')
        else:
            self.subjectDone(node)
            self.depth += 2
            # self.write('[\n' + self.indent())
            self.write('[')
            self.depth -= 1
            # self.predicateList(node, newline=True)
            self.predicateList(node, newline=False)
            # self.write('\n' + self.indent() + ']')
            self.write(' ]')
            self.depth -= 1

        return True

    def s_default(self, subject):  # XXX ordering issues start here
        self.write('\n' + self.indent())
        self.path(subject, SUBJECT)
        self.predicateList(subject)
        self.write(' .')
        return True

    def s_squared(self, subject):  # XXX ordering issues start here
        if (self._references[subject] > 0) or not isinstance(subject, BNode):
            return False
        self.write('\n' + self.indent() + '[]')
        self.predicateList(subject)
        self.write(' .')
        return True

    def serialize(self, stream, base=None, encoding=None,
                  spacious=None, **args):
        super(CustomTurtleSerializer, self).serialize(stream, base, encoding, spacious, **args)
        stream.write(u"# serialized using the nifstd custom serializer\n".encode('ascii'))
