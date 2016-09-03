#!/usr/bin/env python3.5
"""
    Sync the scicrunch registry to a ttl
    file for loading into scigraph for autocomplete. 
"""

import os
from datetime import date

import rdflib
from IPython import embed
from sqlalchemy import create_engine, inspect
from utils import makeGraph, mysql_conn_helper

PREFIXES = {
    'owl':'http://www.w3.org/2002/07/owl#',
    'rdf':'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs':'http://www.w3.org/2000/01/rdf-schema#',
    'skos':'http://www.w3.org/2004/02/skos/core#',
    '':'http://scicrunch.org/resolver/',  # generate base from this directly?
    'obo':'http://purl.obolibrary.org/obo/',
    #'FIXME':'http://fixme.org/',
    'NIF':'http://uri.neuinfo.org/nif/nifstd/',  # for old ids??
    'obo_annot':'http://ontology.neuinfo.org/NIF/Backend/OBO_annotation_properties.owl#',  #FIXME OLD??
    'oboInOwl':'http://www.geneontology.org/formats/oboInOwl#',  # these aren't really from OBO files but they will be friendly known identifiers to people in the community
}

ONTOLOGY_BASE = 'some silly iri'

ONTOLOGY_DEF = {
    'iri':'http://ontology.neuinfo.org/NIF/scicrunch-registry.ttl',
    'label':'scicrunch registry exported ontology',
    'comment':'This file is automatically generated from the SciCrunch resource registry on a weekly basis via https://github.com/tgbugs/pyontutils/blob/master/scr_sync.py.',
    'version':date.today().strftime('%Y-%m-%d'),
}

remap_supers = {
    'Resource':'NIF:nlx_63400',  # FIXME do not want to use : but broken because of defaulting to add : to all scr ids (can fix just not quite yet)
    'Commercial Organization':'NIF:nlx_152342',
    'Organization':'NIF:nlx_152328',
    'University':'NIF:NEMO_0569000',  # UWOTM8

    'Institution':'NIF:birnlex_2085',
    'Institute':'NIF:SIO_000688',
    'Government granting agency':'NIF:birnlex_2431',
}

def make_records(resources, res_cols, field_mapping):
    resources = {id:(scrid, oid, type, status) for id, scrid, oid, type, status in resources}
    res_cols_latest = {}
    versions = {}
    for rid, value_name, value, version in res_cols:
        if rid not in versions:
            versions[(rid, value_name)] = version  # XXX WARNING assumption is that for these fields resources will only ever have ONE but there is no gurantee :( argh myslq

        if version >= versions[(rid, value_name)]:
            res_cols_latest[(rid, value_name)] = (rid, value_name, value)

    res_cols = list(res_cols_latest.values())

    output = {}
        #rc_query = conn.execute('SELECT rid, name, value FROM resource_columns as rc WHERE rc.name IN %s' % str(tuple([n for n in field_mapping if n != 'MULTI'])))
    #for rid, original_id, type_, value_name, value in join_results:
    for rid, value_name, value in res_cols:
        #print(rid, value_name, value)
        scrid, oid, type_, status = resources[rid]
        if scrid.startswith('SCR_'):
            scrid = ':' + scrid  # FIXME
        if scrid not in output:
            output[scrid] = []
        #if 'id' not in [a for a in zip(*output[rid])][0]:
            output[scrid].append(('id', scrid))  # add the empty prefix
            if oid:
                output[scrid].append(('old_id', oid))
            #output[scrid].append(('type', type_))  # this should come via the scigraph cats func
            if status == 'Rejected':
                output[scrid].append(('deprecated', True))
        
        if value_name in field_mapping['MULTI']:
            values = [v.strip() for v in value.split(',')]  # XXX DANGER ZONE
            name = field_mapping['MULTI'][value_name]
            for v in values:
                output[scrid].append((name, v))  # TODO we may want functions here
        else:
            if field_mapping[value_name] == 'definition':
                value = value.replace('\r\n','\n').replace('\r','\n').replace("'''","' ''")  # the ''' replace is because owlapi ttl parser considers """ to match ''' :/ probably need to submit a bug
            elif field_mapping[value_name] == 'superclass':
                if value in remap_supers:
                    value = remap_supers[value]
            output[scrid].append((field_mapping[value_name], value))  # TODO we may want functions here

    return output

field_to_edge = {
    'abbrev':'obo_annot:abbrev',
    'alt_id':'oboInOwl:hasDbXref',
    #'definition':'obo:IAO_0000115',  # FIXME alternate is skos:definition...
    'definition':'skos:definition',
    'id':'rdf:type',
    'label':'rdfs:label',
    'old_id':'oboInOwl:hasDbXref',  # old vs alt id?
    'deprecated':'owl:deprecated',
    'superclass':'rdfs:subClassOf',  # translation required
    'synonym':'obo_annot:synonym',  # FIXME
    'type':'FIXME:type',  # bloody type vs superclass :/ ask james
}

def make_node(id_, field, value):
    if field == 'id':
        value = 'owl:Class'
    #if type(value) == bool:
        #if value:
            #value = rdflib.Literal(True)
        #else:
            #value = rdflib.Literal(False)
    return id_, field_to_edge[field], value


field_mapping = {
    'Resource Name':'label',
    'Description':'definition',
    'Synonyms':'synonyms',
    'Alternate IDs':'alt_ids',
    'Supercategory':'superclass',
    #'Keywords':'keywords'  # don't think we need this
    'MULTI':{'Synonyms':'synonym',
             'Alternate IDs':'alt_id',
             'Abbreviation':'abbrev',
            },
}
def main():
    DB_URI = 'mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db}'
    #config = mysql_conn_helper('mysql5-stage.crbs.ucsd.edu', 'nif_eelg', 'nif_eelg_secure')
    config = mysql_conn_helper('nif-mysql.crbs.ucsd.edu', 'nif_eelg', 'nif_eelg_secure')
    engine = create_engine(DB_URI.format(**config))
    config = None  # all weakrefs should be gone by now?
    del(config)  # i wonder whether this actually cleans it up when using **config
    insp = inspect(engine)
    #names = [c['name'] for c in insp.get_columns('registry')]
    #resource_columns = [c['name'] for c in insp.get_columns('resource_columns')]
    #resource_data = [c['name'] for c in insp.get_columns('resource_data')]
    #resource_fields = [c['name'] for c in insp.get_columns('resource_fields')]
    #resources = [c['name'] for c in insp.get_columns('resources')]
    #conn.execute('SELECT * from registry;')
    if 1:
    #with engine.connect() as conn:
        conn = engine
        tables = ('resource_columns', 'resource_data', 'resource_fields', 'resources')
        data = {t:([c['name'] for c in insp.get_columns(t)], conn.execute('SELECT * from %s limit 20;' % t).fetchall()) for t in tables}
        all_fields = [n[0] for n in conn.execute('SELECT distinct(name) FROM resource_fields;').fetchall()]

        #query = conn.execute('SELECT r.rid, r.original_id, r.type, rc.name, rc.value from resources as r JOIN'
                            #' resource_columns as rc ON r.id=rc.rid'
                            #' WHERE rc.name IN %s limit 1000;' % str(tuple([n for n in field_mapping if n != 'MULTI'])))  # XXX DANGER THIS QUERY IS O(x^n) :x
                            #' ORDER BY r.rid limit 2000;'

        #query = conn.execute('SELECT r.rid, r.original_id, r.type, rc.name, rc.value from resource_columns as rc JOIN'
                             #' resources as r ON rc.rid=r.id'
                             #' WHERE rc.name IN %s;' % str(tuple([n for n in field_mapping if n != 'MULTI'])))  # XXX DANGER why does > 2000 limit break stuff?

        #join = query.fetchall()

        #embed()
        #return
        #print('running join')
        print('running 1')
        r_query = conn.execute('SELECT id, rid, original_id, type, status FROM resources WHERE id < 16000;')  # avoid the various test entries :(
        print('fetching 1 ')
        r = r_query.fetchall()
        print('running 2')
        rc_query = conn.execute('SELECT rid, name, value, version FROM resource_columns as rc WHERE rc.rid < 16000 AND rc.name IN %s;' % str(tuple([n for n in field_mapping if n != 'MULTI'])))
        print('fetching 2')
        rc = rc_query.fetchall()

        #embed()
        #return

    r.append( (-100, 'NIF:nlx_63400', 'nlx_63400', 'Resource', 'Curated') )
    r.append( (-101, 'NIF:nlx_152342', 'nlx_152342', 'Organization', 'Curated') )
    r.append( (-102, 'NIF:nlx_152328', 'nlx_152328', 'Organization', 'Curated') )
    r.append( (-103, 'NIF:NEMO_0569000', 'NEMO_0569000', 'Institution', 'Curated') )
    r.append( (-104, 'NIF:birnlex_2431', 'birnlex_2431', 'Institution', 'Curated') )
    r.append( (-105, 'NIF:SIO_000688', 'SIO_000688', 'Institution', 'Curated') )
    r.append( (-106, 'NIF:birnlex_2085', 'birnlex_2085', 'Institution', 'Curated') )
    rc.append( (-100, 'Resource Name', 'Resource', 1) )
    rc.append( (-101, 'Resource Name', 'Commercial Organization', 1) )
    rc.append( (-102, 'Resource Name', 'Organization', 1) )
    rc.append( (-103, 'Resource Name', 'University', 1) )
    rc.append( (-104, 'Resource Name', 'Government granting agency', 1) )
    rc.append( (-105, 'Resource Name', 'Institute', 1) )
    rc.append( (-106, 'Resource Name', 'Institution', 1) )
    rc.append( (-101, 'Supercategory', 'NIF:nlx_152328', 1) )  # TODO extract this more intelligently from remap supers please

    output = make_records(r, rc, field_mapping)
    print('Fetching and data prep done.')
    g = makeGraph('scicrunch-registry', PREFIXES)

    # ontology metadata
    ontid = ONTOLOGY_DEF['iri']
    g.add_node(ontid, rdflib.RDF.type, rdflib.OWL.Ontology)
    g.add_node(ontid, rdflib.RDFS.label, ONTOLOGY_DEF['label'])
    g.add_node(ontid, rdflib.RDFS.comment, ONTOLOGY_DEF['comment'])
    g.add_node(ontid, rdflib.OWL.versionInfo, ONTOLOGY_DEF['version'])

    for id_, rec in output.items():
        for field, value in rec:
            #print(field, value)
            if not value:  # don't add empty edges  # FIXME issue with False literal
                print('caught an empty value on field', id_, field)
                continue
            if field != 'id' and str(value) in id_:
            #if field == 'alt_id' and id_[1:] == value:
                print('caught a mainid appearing as altid', field, value)
                continue
            g.add_node(*make_node(id_, field, value))

    g.write()

if __name__ == '__main__':
    main()
