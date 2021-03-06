#!/usr/bin/env python3.6
""" Run in NIF-Ontology/ttl/ """

import os
import json
import yaml
from glob import glob
import rdflib
from pyontutils.utils import makeGraph, makePrefixes, memoryCheck, noneMembers  # TODO make prefixes needs an all...
from pyontutils.hierarchies import creatTree
from collections import namedtuple
from IPython import embed

if os.getcwd() == os.path.expanduser('~/git/NIF-Ontology/ttl'):
    memoryCheck(2665488384)

Query = namedtuple('Query', ['root','relationshipType','direction','depth'])

graph = rdflib.Graph()

done = []
for f in glob('*/*/*.ttl') + glob('*/*.ttl') + glob('*.ttl'):
    print(f)
    done.append(os.path.basename(f))
    graph.parse(f, format='turtle')

def repeat(dobig=False):  # we don't really know when to stop, so just adjust
    for s, o in graph.subject_objects(rdflib.OWL.imports):
        if os.path.basename(o) not in done and o not in done:
        #if (o, rdflib.RDF.type, rdflib.OWL.Ontology) not in graph:
            print(o)
            done.append(o)
            ext = os.path.splitext(o)[1]
            fmt = 'turtle' if ext == '.ttl' else 'xml'
            if noneMembers(o, 'go.owl', 'uberon.owl', 'pr.owl', 'doid.owl', 'taxslim.owl') or dobig:
                graph.parse(o, format=fmt)

for i in range(4):
    repeat(True)

with open(os.path.expanduser('~/git/NIF-Ontology/scigraph/nifstd_curie_map.yaml'), 'rt') as f:
    wat = yaml.load(f)
vals = set(wat.values())

mg = makeGraph('nifall', makePrefixes('owl', 'skos', 'oboInOwl'), graph=graph)
mg.del_namespace('')

old_namespaces = list(graph.namespaces())
ng_ = makeGraph('', prefixes=makePrefixes('oboInOwl', 'skos'), graph=rdflib.Graph())
[ng_.g.add(t) for t in mg.g]
[ng_.add_namespace(n, p) for n, p in wat.items() if n != '']
#[mg.add_namespace(n, p) for n, p in old_namespaces if n.startswith('ns') or n.startswith('default')]
#[mg.del_namespace(n) for n in list(mg.namespaces)]
#graph.namespace_manager.reset()
#[mg.add_namespace(n, p) for n, p in wat.items() if n != '']

def for_burak(ng):
    syn_predicates = (ng.expand('OBOANN:synonym'),
                      ng.expand('OBOANN:acronym'),
                      ng.expand('OBOANN:abbrev'),
                      ng.expand('oboInOwl:hasExactSynonym'),
                      ng.expand('oboInOwl:hasNarrowSynonym'),
                      ng.expand('oboInOwl:hasBroadSynonym'),
                      ng.expand('oboInOwl:hasRelatedSynonym'),
                      ng.expand('skos:prefLabel'),
                      rdflib.URIRef('http://purl.obolibrary.org/obo/go#systematic_synonym'),
                     )
    lab_predicates = rdflib.RDFS.label,
    graph = ng.g
    for s in graph.subjects(rdflib.RDF.type, rdflib.OWL.Class):
        if not isinstance(s, rdflib.BNode):
            curie = ng.qname(s)
            labels = [o for p in lab_predicates for o in graph.objects(s, p)
                      if not isinstance(o, rdflib.BNode)]
            synonyms = [o for p in syn_predicates for o in graph.objects(s, p)
                        if not isinstance(o, rdflib.BNode)]
            parents = [ng.qname(o) for o in graph.objects(s, rdflib.RDFS.subClassOf)
                       if not isinstance(o, rdflib.BNode)]
            yield [curie, labels, synonyms, parents]

#globals()['for_burak'] = for_burak
records = {c:[l, s, p] for c, l, s, p in for_burak(ng_) if l or s}
with open(os.path.expanduser('~/files/ontology-classes-with-labels-synonyms-parents.json'), 'wt') as f:
          json.dump(records, f, sort_keys=True, indent=2)

mg.add_known_namespace('NIFTTL')
j = mg.make_scigraph_json('owl:imports', direct=True)
#asdf = sorted(set(_ for t in graph for _ in t if type(_) == rdflib.URIRef))  # this snags a bunch of other URIs
#asdf = sorted(set(_ for _ in graph.subjects() if type(_) != rdflib.BNode))
asdf = set(_ for t in graph.subject_predicates() for _ in t if type(_) == rdflib.URIRef)
prefs = set(_.rsplit('#', 1)[0] + '#' if '#' in _
                   else (_.rsplit('_',1)[0] + '_' if '_' in _
                         else _.rsplit('/',1)[0] + '/') for _ in asdf)
nots = set(_ for _ in prefs if _ not in vals)
sos = set(prefs) - set(nots)

print(len(prefs))
t, te = creatTree(*Query('NIFTTL:nif.ttl', 'owl:imports', 'OUTGOING', 30), json=j)
embed()
print(t)
