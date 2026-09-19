#!/usr/bin/env python3
"""Validate nineteen pinned GeoTools schema resource capsules, never executable jars.

Resource paths and historical Ant source URLs come from the unchanged owned
GeoTools 34.5 packaging POMs. This module neither runs those POMs nor contacts
those URLs. Accepted bytes are retained source/data candidates, not source-built
Java artifacts or license approval. XML comments/notices remain in original bytes.
"""
import hashlib
import io
from pathlib import PurePosixPath
import re
import stat
import xml.etree.ElementTree as ET
from xml.parsers import expat
import zipfile
import zlib


class SchemaResourceError(ValueError):
    """The capsule does not meet the bounded resource-only acquisition policy."""


MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_MEMBERS = 1024
MAX_COMPRESSION_RATIO = 200
_SEGMENT = re.compile(r"[A-Za-z0-9_.+~-]+\Z")
_NOTICE = re.compile(r"(?:LICENSE|NOTICE|COPYING|COPYRIGHT)(?:[-_.][A-Za-z0-9_.+-]+)?\Z", re.I)
_CHECKSUMS = ("sha1", "sha256", "sha512", "md5")
_NS = {"m": "http://maven.apache.org/POM/4.0.0"}

# Exact resources from nineteen reviewed, parentless source packaging POMs.
RESOURCES = {'org.geotools.schemas:cgiutilities-1.0:1.0.0-4': {'org/geosciml/www/cgiutilities/1.0/xsd/cgiUtilities.xsd': 'http://www.geosciml.org/cgiutilities/1.0/xsd/cgiUtilities.xsd',
                                                   'org/geosciml/www/cgiutilities/1.0/xsd/primitiveTypes.xsd': 'http://www.geosciml.org/cgiutilities/1.0/xsd/primitiveTypes.xsd'},
 'org.geotools.schemas:earthresourceml-1.1:1.1.0-3': {'org/earthresourceml/www/earthresourceml/1.1/xsd/earthResource.xsd': 'http://www.earthresourceml.org/earthresourceml/1.1/xsd/earthResource.xsd',
                                                      'org/earthresourceml/www/earthresourceml/1.1/xsd/mine.xsd': 'http://www.earthresourceml.org/earthresourceml/1.1/xsd/mine.xsd',
                                                      'org/earthresourceml/www/earthresourceml/1.1/xsd/mineralOccurrence.xsd': 'http://www.earthresourceml.org/earthresourceml/1.1/xsd/mineralOccurrence.xsd'},
 'org.geotools.schemas:filter-1.1:1.1.1-2': {'net/opengis/schemas/filter/1.1.0/expr.xsd': 'http://schemas.opengis.net/filter/1.1.0/expr.xsd',
                                             'net/opengis/schemas/filter/1.1.0/filter.xsd': 'http://schemas.opengis.net/filter/1.1.0/filter.xsd',
                                             'net/opengis/schemas/filter/1.1.0/filterCapabilities.xsd': 'http://schemas.opengis.net/filter/1.1.0/filterCapabilities.xsd',
                                             'net/opengis/schemas/filter/1.1.0/sort.xsd': 'http://schemas.opengis.net/filter/1.1.0/sort.xsd'},
 'org.geotools.schemas:filter-2.0:2.0.0-2': {'net/opengis/schemas/filter/2.0/expr.xsd': 'http://schemas.opengis.net/filter/2.0/expr.xsd',
                                             'net/opengis/schemas/filter/2.0/filter.xsd': 'http://schemas.opengis.net/filter/2.0/filter.xsd',
                                             'net/opengis/schemas/filter/2.0/filterAll.xsd': 'http://schemas.opengis.net/filter/2.0/filterAll.xsd',
                                             'net/opengis/schemas/filter/2.0/filterCapabilities.xsd': 'http://schemas.opengis.net/filter/2.0/filterCapabilities.xsd',
                                             'net/opengis/schemas/filter/2.0/query.xsd': 'http://schemas.opengis.net/filter/2.0/query.xsd',
                                             'net/opengis/schemas/filter/2.0/sort.xsd': 'http://schemas.opengis.net/filter/2.0/sort.xsd'},
 'org.geotools.schemas:geosciml-2.0:2.0.2-4': {'org/geosciml/www/geosciml/2.0/xsd/GeologicUnitType.xml': 'http://www.geosciml.org/geosciml/2.0/xsd/GeologicUnitType.xml',
                                               'org/geosciml/www/geosciml/2.0/xsd/borehole.xsd': 'http://www.geosciml.org/geosciml/2.0/xsd/borehole.xsd',
                                               'org/geosciml/www/geosciml/2.0/xsd/collection.xsd': 'http://www.geosciml.org/geosciml/2.0/xsd/collection.xsd',
                                               'org/geosciml/www/geosciml/2.0/xsd/earthMaterial.xsd': 'http://www.geosciml.org/geosciml/2.0/xsd/earthMaterial.xsd',
                                               'org/geosciml/www/geosciml/2.0/xsd/fossil.xsd': 'http://www.geosciml.org/geosciml/2.0/xsd/fossil.xsd',
                                               'org/geosciml/www/geosciml/2.0/xsd/geologicAge.xsd': 'http://www.geosciml.org/geosciml/2.0/xsd/geologicAge.xsd',
                                               'org/geosciml/www/geosciml/2.0/xsd/geologicFeature.xsd': 'http://www.geosciml.org/geosciml/2.0/xsd/geologicFeature.xsd',
                                               'org/geosciml/www/geosciml/2.0/xsd/geologicRelation.xsd': 'http://www.geosciml.org/geosciml/2.0/xsd/geologicRelation.xsd',
                                               'org/geosciml/www/geosciml/2.0/xsd/geologicStructure.xsd': 'http://www.geosciml.org/geosciml/2.0/xsd/geologicStructure.xsd',
                                               'org/geosciml/www/geosciml/2.0/xsd/geologicUnit.xsd': 'http://www.geosciml.org/geosciml/2.0/xsd/geologicUnit.xsd',
                                               'org/geosciml/www/geosciml/2.0/xsd/geosciml.xsd': 'http://www.geosciml.org/geosciml/2.0/xsd/geosciml.xsd',
                                               'org/geosciml/www/geosciml/2.0/xsd/value.xsd': 'http://www.geosciml.org/geosciml/2.0/xsd/value.xsd',
                                               'org/geosciml/www/geosciml/2.0/xsd/vocabulary.xsd': 'http://www.geosciml.org/geosciml/2.0/xsd/vocabulary.xsd'},
 'org.geotools.schemas:gml-3.1:3.1.1-4': {'net/opengis/schemas/gml/3.1.1/base/basicTypes.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/basicTypes.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/coordinateOperations.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/coordinateOperations.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/coordinateReferenceSystems.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/coordinateReferenceSystems.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/coordinateSystems.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/coordinateSystems.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/coverage.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/coverage.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/dataQuality.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/dataQuality.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/datums.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/datums.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/defaultStyle.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/defaultStyle.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/dictionary.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/dictionary.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/direction.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/direction.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/dynamicFeature.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/dynamicFeature.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/feature.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/feature.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/geometryAggregates.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/geometryAggregates.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/geometryBasic0d1d.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/geometryBasic0d1d.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/geometryBasic2d.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/geometryBasic2d.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/geometryComplexes.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/geometryComplexes.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/geometryPrimitives.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/geometryPrimitives.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/gml.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/gml.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/gmlBase.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/gmlBase.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/grids.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/grids.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/measures.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/measures.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/observation.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/observation.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/referenceSystems.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/referenceSystems.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/temporal.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/temporal.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/temporalReferenceSystems.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/temporalReferenceSystems.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/temporalTopology.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/temporalTopology.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/topology.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/topology.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/units.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/units.xsd',
                                          'net/opengis/schemas/gml/3.1.1/base/valueObjects.xsd': 'http://schemas.opengis.net/gml/3.1.1/base/valueObjects.xsd',
                                          'net/opengis/schemas/gml/3.1.1/smil/smil20-language.xsd': 'http://schemas.opengis.net/gml/3.1.1/smil/smil20-language.xsd',
                                          'net/opengis/schemas/gml/3.1.1/smil/smil20.xsd': 'http://schemas.opengis.net/gml/3.1.1/smil/smil20.xsd',
                                          'net/opengis/schemas/gml/3.1.1/smil/xml-mod.xsd': 'http://schemas.opengis.net/gml/3.1.1/smil/xml-mod.xsd'},
 'org.geotools.schemas:gml-3.2:3.2.1-1': {'net/opengis/schemas/gml/3.2.1/ReadMe.txt': 'http://schemas.opengis.net/gml/3.2.1/ReadMe.txt',
                                          'net/opengis/schemas/gml/3.2.1/SchematronConstraints.xml': 'http://schemas.opengis.net/gml/3.2.1/SchematronConstraints.xml',
                                          'net/opengis/schemas/gml/3.2.1/basicTypes.xsd': 'http://schemas.opengis.net/gml/3.2.1/basicTypes.xsd',
                                          'net/opengis/schemas/gml/3.2.1/coordinateOperations.xsd': 'http://schemas.opengis.net/gml/3.2.1/coordinateOperations.xsd',
                                          'net/opengis/schemas/gml/3.2.1/coordinateReferenceSystems.xsd': 'http://schemas.opengis.net/gml/3.2.1/coordinateReferenceSystems.xsd',
                                          'net/opengis/schemas/gml/3.2.1/coordinateSystems.xsd': 'http://schemas.opengis.net/gml/3.2.1/coordinateSystems.xsd',
                                          'net/opengis/schemas/gml/3.2.1/coverage.xsd': 'http://schemas.opengis.net/gml/3.2.1/coverage.xsd',
                                          'net/opengis/schemas/gml/3.2.1/datums.xsd': 'http://schemas.opengis.net/gml/3.2.1/datums.xsd',
                                          'net/opengis/schemas/gml/3.2.1/defaultStyle.xsd': 'http://schemas.opengis.net/gml/3.2.1/defaultStyle.xsd',
                                          'net/opengis/schemas/gml/3.2.1/deprecatedTypes.xsd': 'http://schemas.opengis.net/gml/3.2.1/deprecatedTypes.xsd',
                                          'net/opengis/schemas/gml/3.2.1/dictionary.xsd': 'http://schemas.opengis.net/gml/3.2.1/dictionary.xsd',
                                          'net/opengis/schemas/gml/3.2.1/direction.xsd': 'http://schemas.opengis.net/gml/3.2.1/direction.xsd',
                                          'net/opengis/schemas/gml/3.2.1/dynamicFeature.xsd': 'http://schemas.opengis.net/gml/3.2.1/dynamicFeature.xsd',
                                          'net/opengis/schemas/gml/3.2.1/feature.xsd': 'http://schemas.opengis.net/gml/3.2.1/feature.xsd',
                                          'net/opengis/schemas/gml/3.2.1/geometryAggregates.xsd': 'http://schemas.opengis.net/gml/3.2.1/geometryAggregates.xsd',
                                          'net/opengis/schemas/gml/3.2.1/geometryBasic0d1d.xsd': 'http://schemas.opengis.net/gml/3.2.1/geometryBasic0d1d.xsd',
                                          'net/opengis/schemas/gml/3.2.1/geometryBasic2d.xsd': 'http://schemas.opengis.net/gml/3.2.1/geometryBasic2d.xsd',
                                          'net/opengis/schemas/gml/3.2.1/geometryComplexes.xsd': 'http://schemas.opengis.net/gml/3.2.1/geometryComplexes.xsd',
                                          'net/opengis/schemas/gml/3.2.1/geometryPrimitives.xsd': 'http://schemas.opengis.net/gml/3.2.1/geometryPrimitives.xsd',
                                          'net/opengis/schemas/gml/3.2.1/gml.xsd': 'http://schemas.opengis.net/gml/3.2.1/gml.xsd',
                                          'net/opengis/schemas/gml/3.2.1/gmlBase.xsd': 'http://schemas.opengis.net/gml/3.2.1/gmlBase.xsd',
                                          'net/opengis/schemas/gml/3.2.1/gml_3_2_1-ReadMe.txt': 'http://schemas.opengis.net/gml/3.2.1/gml_3_2_1-ReadMe.txt',
                                          'net/opengis/schemas/gml/3.2.1/grids.xsd': 'http://schemas.opengis.net/gml/3.2.1/grids.xsd',
                                          'net/opengis/schemas/gml/3.2.1/measures.xsd': 'http://schemas.opengis.net/gml/3.2.1/measures.xsd',
                                          'net/opengis/schemas/gml/3.2.1/observation.xsd': 'http://schemas.opengis.net/gml/3.2.1/observation.xsd',
                                          'net/opengis/schemas/gml/3.2.1/referenceSystems.xsd': 'http://schemas.opengis.net/gml/3.2.1/referenceSystems.xsd',
                                          'net/opengis/schemas/gml/3.2.1/temporal.xsd': 'http://schemas.opengis.net/gml/3.2.1/temporal.xsd',
                                          'net/opengis/schemas/gml/3.2.1/temporalReferenceSystems.xsd': 'http://schemas.opengis.net/gml/3.2.1/temporalReferenceSystems.xsd',
                                          'net/opengis/schemas/gml/3.2.1/temporalTopology.xsd': 'http://schemas.opengis.net/gml/3.2.1/temporalTopology.xsd',
                                          'net/opengis/schemas/gml/3.2.1/topology.xsd': 'http://schemas.opengis.net/gml/3.2.1/topology.xsd',
                                          'net/opengis/schemas/gml/3.2.1/units.xsd': 'http://schemas.opengis.net/gml/3.2.1/units.xsd',
                                          'net/opengis/schemas/gml/3.2.1/valueObjects.xsd': 'http://schemas.opengis.net/gml/3.2.1/valueObjects.xsd'},
 'org.geotools.schemas:ic-2.0:2.0.0-3': {'net/opengis/schemas/ic/2.0/IC-ISM-v2.xsd': 'http://schemas.opengis.net/ic/2.0/IC-ISM-v2.xsd'},
 'org.geotools.schemas:iso-19139-2007:1.0.0-1': {'net/opengis/schemas/iso/19139/20070417/gco/basicTypes.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gco/basicTypes.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gco/gco.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gco/gco.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gco/gcoBase.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gco/gcoBase.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/applicationSchema.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/applicationSchema.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/citation.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/citation.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/constraints.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/constraints.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/content.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/content.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/dataQuality.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/dataQuality.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/distribution.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/distribution.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/extent.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/extent.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/freeText.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/freeText.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/gmd.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/gmd.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/identification.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/identification.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/maintenance.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/maintenance.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/metadataApplication.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/metadataApplication.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/metadataEntity.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/metadataEntity.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/metadataExtension.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/metadataExtension.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/portrayalCatalogue.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/portrayalCatalogue.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/referenceSystem.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/referenceSystem.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmd/spatialRepresentation.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmd/spatialRepresentation.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmx/catalogues.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmx/catalogues.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmx/codelistItem.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmx/codelistItem.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmx/crsItem.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmx/crsItem.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmx/extendedTypes.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmx/extendedTypes.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmx/gmx.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmx/gmx.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmx/gmxUsage.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmx/gmxUsage.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gmx/uomItem.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gmx/uomItem.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gsr/gsr.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gsr/gsr.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gsr/spatialReferencing.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gsr/spatialReferencing.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gss/geometry.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gss/geometry.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gss/gss.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gss/gss.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gts/gts.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gts/gts.xsd',
                                                 'net/opengis/schemas/iso/19139/20070417/gts/temporalObjects.xsd': 'http://schemas.opengis.net/iso/19139/20070417/gts/temporalObjects.xsd'},
 'org.geotools.schemas:om-1.0:1.0.0-4': {'net/opengis/schemas/om/1.0.0/observation.xsd': 'http://schemas.opengis.net/om/1.0.0/observation.xsd',
                                         'net/opengis/schemas/om/1.0.0/om.xsd': 'http://schemas.opengis.net/om/1.0.0/om.xsd'},
 'org.geotools.schemas:ows-1.0:1.0.0-2': {'net/opengis/schemas/ows/1.0.0/ows19115subset.xsd': 'http://schemas.opengis.net/ows/1.0.0/ows19115subset.xsd',
                                          'net/opengis/schemas/ows/1.0.0/owsAll.xsd': 'http://schemas.opengis.net/ows/1.0.0/owsAll.xsd',
                                          'net/opengis/schemas/ows/1.0.0/owsCommon.xsd': 'http://schemas.opengis.net/ows/1.0.0/owsCommon.xsd',
                                          'net/opengis/schemas/ows/1.0.0/owsDataIdentification.xsd': 'http://schemas.opengis.net/ows/1.0.0/owsDataIdentification.xsd',
                                          'net/opengis/schemas/ows/1.0.0/owsExceptionReport.xsd': 'http://schemas.opengis.net/ows/1.0.0/owsExceptionReport.xsd',
                                          'net/opengis/schemas/ows/1.0.0/owsGetCapabilities.xsd': 'http://schemas.opengis.net/ows/1.0.0/owsGetCapabilities.xsd',
                                          'net/opengis/schemas/ows/1.0.0/owsOperationsMetadata.xsd': 'http://schemas.opengis.net/ows/1.0.0/owsOperationsMetadata.xsd',
                                          'net/opengis/schemas/ows/1.0.0/owsServiceIdentification.xsd': 'http://schemas.opengis.net/ows/1.0.0/owsServiceIdentification.xsd',
                                          'net/opengis/schemas/ows/1.0.0/owsServiceProvider.xsd': 'http://schemas.opengis.net/ows/1.0.0/owsServiceProvider.xsd'},
 'org.geotools.schemas:ows-1.1:1.1.0-1': {'net/opengis/schemas/ows/1.1.0/ows19115subset.xsd': 'http://schemas.opengis.net/ows/1.1.0/ows19115subset.xsd',
                                          'net/opengis/schemas/ows/1.1.0/owsAll.xsd': 'http://schemas.opengis.net/ows/1.1.0/owsAll.xsd',
                                          'net/opengis/schemas/ows/1.1.0/owsCommon.xsd': 'http://schemas.opengis.net/ows/1.1.0/owsCommon.xsd',
                                          'net/opengis/schemas/ows/1.1.0/owsContents.xsd': 'http://schemas.opengis.net/ows/1.1.0/owsContents.xsd',
                                          'net/opengis/schemas/ows/1.1.0/owsDataIdentification.xsd': 'http://schemas.opengis.net/ows/1.1.0/owsDataIdentification.xsd',
                                          'net/opengis/schemas/ows/1.1.0/owsDomainType.xsd': 'http://schemas.opengis.net/ows/1.1.0/owsDomainType.xsd',
                                          'net/opengis/schemas/ows/1.1.0/owsExceptionReport.xsd': 'http://schemas.opengis.net/ows/1.1.0/owsExceptionReport.xsd',
                                          'net/opengis/schemas/ows/1.1.0/owsGetCapabilities.xsd': 'http://schemas.opengis.net/ows/1.1.0/owsGetCapabilities.xsd',
                                          'net/opengis/schemas/ows/1.1.0/owsGetResourceByID.xsd': 'http://schemas.opengis.net/ows/1.1.0/owsGetResourceByID.xsd',
                                          'net/opengis/schemas/ows/1.1.0/owsInputOutputData.xsd': 'http://schemas.opengis.net/ows/1.1.0/owsInputOutputData.xsd',
                                          'net/opengis/schemas/ows/1.1.0/owsManifest.xsd': 'http://schemas.opengis.net/ows/1.1.0/owsManifest.xsd',
                                          'net/opengis/schemas/ows/1.1.0/owsOperationsMetadata.xsd': 'http://schemas.opengis.net/ows/1.1.0/owsOperationsMetadata.xsd',
                                          'net/opengis/schemas/ows/1.1.0/owsServiceIdentification.xsd': 'http://schemas.opengis.net/ows/1.1.0/owsServiceIdentification.xsd',
                                          'net/opengis/schemas/ows/1.1.0/owsServiceProvider.xsd': 'http://schemas.opengis.net/ows/1.1.0/owsServiceProvider.xsd'},
 'org.geotools.schemas:sampling-1.0:1.0.0-4': {'net/opengis/schemas/sampling/1.0.0/LUTgeodesy.xsd': 'http://schemas.opengis.net/sampling/1.0.0/LUTgeodesy.xsd',
                                               'net/opengis/schemas/sampling/1.0.0/sampling.xsd': 'http://schemas.opengis.net/sampling/1.0.0/sampling.xsd',
                                               'net/opengis/schemas/sampling/1.0.0/samplingBase.xsd': 'http://schemas.opengis.net/sampling/1.0.0/samplingBase.xsd',
                                               'net/opengis/schemas/sampling/1.0.0/samplingManifold.xsd': 'http://schemas.opengis.net/sampling/1.0.0/samplingManifold.xsd',
                                               'net/opengis/schemas/sampling/1.0.0/specimen.xsd': 'http://schemas.opengis.net/sampling/1.0.0/specimen.xsd',
                                               'net/opengis/schemas/sampling/1.0.0/surveyProcedure.xsd': 'http://schemas.opengis.net/sampling/1.0.0/surveyProcedure.xsd'},
 'org.geotools.schemas:sensorML-1.0:1.0.1-4': {'net/opengis/schemas/sensorML/1.0.1/base.xsd': 'http://schemas.opengis.net/sensorML/1.0.1/base.xsd',
                                               'net/opengis/schemas/sensorML/1.0.1/method.xsd': 'http://schemas.opengis.net/sensorML/1.0.1/method.xsd',
                                               'net/opengis/schemas/sensorML/1.0.1/process.xsd': 'http://schemas.opengis.net/sensorML/1.0.1/process.xsd',
                                               'net/opengis/schemas/sensorML/1.0.1/sensorML.xsd': 'http://schemas.opengis.net/sensorML/1.0.1/sensorML.xsd',
                                               'net/opengis/schemas/sensorML/1.0.1/system.xsd': 'http://schemas.opengis.net/sensorML/1.0.1/system.xsd'},
 'org.geotools.schemas:sweCommon-1.0:1.0.1-4': {'net/opengis/schemas/sweCommon/1.0.1/aggregateTypes.xsd': 'http://schemas.opengis.net/sweCommon/1.0.1/aggregateTypes.xsd',
                                                'net/opengis/schemas/sweCommon/1.0.1/basicTypes.xsd': 'http://schemas.opengis.net/sweCommon/1.0.1/basicTypes.xsd',
                                                'net/opengis/schemas/sweCommon/1.0.1/curveTypes.xsd': 'http://schemas.opengis.net/sweCommon/1.0.1/curveTypes.xsd',
                                                'net/opengis/schemas/sweCommon/1.0.1/data.xsd': 'http://schemas.opengis.net/sweCommon/1.0.1/data.xsd',
                                                'net/opengis/schemas/sweCommon/1.0.1/encoding.xsd': 'http://schemas.opengis.net/sweCommon/1.0.1/encoding.xsd',
                                                'net/opengis/schemas/sweCommon/1.0.1/phenomenon.xsd': 'http://schemas.opengis.net/sweCommon/1.0.1/phenomenon.xsd',
                                                'net/opengis/schemas/sweCommon/1.0.1/positionTypes.xsd': 'http://schemas.opengis.net/sweCommon/1.0.1/positionTypes.xsd',
                                                'net/opengis/schemas/sweCommon/1.0.1/simpleTypes.xsd': 'http://schemas.opengis.net/sweCommon/1.0.1/simpleTypes.xsd',
                                                'net/opengis/schemas/sweCommon/1.0.1/swe.xsd': 'http://schemas.opengis.net/sweCommon/1.0.1/swe.xsd',
                                                'net/opengis/schemas/sweCommon/1.0.1/temporalAggregates.xsd': 'http://schemas.opengis.net/sweCommon/1.0.1/temporalAggregates.xsd',
                                                'net/opengis/schemas/sweCommon/1.0.1/xmlData.xsd': 'http://schemas.opengis.net/sweCommon/1.0.1/xmlData.xsd'},
 'org.geotools.schemas:wfs-1.1:1.1.2-2': {'net/opengis/schemas/wfs/1.1.0/wfs.xsd': 'http://schemas.opengis.net/wfs/1.1.0/wfs.xsd'},
 'org.geotools.schemas:wfs-2.0:2.0.0-2': {'net/opengis/schemas/wfs/2.0/wfs.xsd': 'http://schemas.opengis.net/wfs/2.0/wfs.xsd'},
 'org.geotools.schemas:xlink-1.0:1.0.0-3': {'net/opengis/schemas/xlink/1.0.0/xlinks.xsd': 'http://schemas.opengis.net/xlink/1.0.0/xlinks.xsd'},
 'org.geotools.schemas:xml-1.0:1.0.0-3': {'org/w3/www/2001/xml.xsd': 'http://www.w3.org/2001/xml.xsd'}}


def schema_coordinate(maven_path: str) -> str | None:
    for gav in RESOURCES:
        group, artifact, version = gav.split(":")
        expected = f"{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}.jar"
        if maven_path == expected:
            return gav
    return None


def schema_checksum(maven_path: str) -> tuple[str, str] | None:
    for algorithm in _CHECKSUMS:
        suffix = "." + algorithm
        if maven_path.endswith(suffix) and schema_coordinate(maven_path[:-len(suffix)]):
            return maven_path[:-len(suffix)], algorithm
    return None


def _xml(data: bytes):
    # Expat callbacks catch declarations regardless of XML byte encoding. No DTD,
    # entities, stylesheet instruction, network fetch or XInclude execution occurs.
    parser = expat.ParserCreate()

    def forbidden(*args):
        raise SchemaResourceError("XML declarations/entities/processing instructions are forbidden")

    parser.StartDoctypeDeclHandler = forbidden
    parser.EntityDeclHandler = forbidden
    parser.ExternalEntityRefHandler = forbidden
    parser.ProcessingInstructionHandler = forbidden
    try:
        parser.Parse(data, True)
        return ET.fromstring(data)
    except (expat.ExpatError, ET.ParseError) as error:
        raise SchemaResourceError("invalid XML resource") from error


def _text(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError as error:
        raise SchemaResourceError("resource metadata/notice must be UTF-8 text") from error
    if any(ord(char) < 32 and char not in "\t\r\n" for char in text):
        raise SchemaResourceError("resource metadata/notice contains binary control bytes")
    if text.lstrip().startswith("#!"):
        raise SchemaResourceError("script content in resource metadata/notice")
    return text


def _manifest(data: bytes) -> None:
    allowed = {"Manifest-Version", "Archiver-Version", "Created-By", "Built-By",
               "Build-Jdk", "Build-Jdk-Spec", "Implementation-Title",
               "Implementation-Version", "Implementation-Vendor", "Implementation-Vendor-Id",
               "Specification-Title", "Specification-Version", "Specification-Vendor",
               "Automatic-Module-Name"}
    previous = False
    for line in _text(data).splitlines():
        if not line:
            previous = False
        elif line.startswith(" "):
            if not previous:
                raise SchemaResourceError("invalid manifest continuation")
        else:
            key, separator, unused = line.partition(": ")
            if not separator or key not in allowed:
                raise SchemaResourceError("manifest contains a non-inert or unknown attribute")
            previous = True


def _pom(data: bytes, gav: str) -> None:
    root = _xml(data)
    if root.tag != "{" + _NS["m"] + "}project":
        raise SchemaResourceError("embedded POM is not a Maven project")
    actual = ":".join(root.findtext("m:" + key, "", _NS).strip()
                      for key in ("groupId", "artifactId", "version"))
    if actual != gav or root.find("m:parent", _NS) is not None:
        raise SchemaResourceError("embedded POM coordinate differs from requested capsule")
    properties = {entry.get("name"): entry.get("value", "") for entry in root.iter()
                  if entry.tag.rsplit("}", 1)[-1] == "property"}
    declarations = {}
    for entry in root.iter():
        if entry.tag.rsplit("}", 1)[-1] != "get":
            continue
        values = [entry.get("dest", ""), entry.get("src", "")]
        for index, value in enumerate(values):
            for unused in range(8):
                before = value
                for key, replacement in properties.items():
                    value = value.replace("${" + str(key) + "}", replacement)
                if value == before:
                    break
            values[index] = value
        destination, url = values
        prefix = "${project.build.outputDirectory}/"
        if not destination.startswith(prefix):
            raise SchemaResourceError("embedded POM resource destination differs from owned recipe")
        relative = destination[len(prefix):]
        if relative in declarations:
            raise SchemaResourceError("duplicate embedded POM resource declaration")
        declarations[relative] = url
    if declarations and declarations != RESOURCES[gav]:
        raise SchemaResourceError("embedded POM resource recipe differs from owned source")


def _properties(data: bytes, gav: str) -> None:
    actual = {}
    for line in _text(data).splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!")):
            continue
        key, separator, value = line.partition("=")
        if not separator or key in actual or key not in {"groupId", "artifactId", "version"}:
            raise SchemaResourceError("invalid embedded Maven properties")
        actual[key] = value
    if ":".join(actual.get(key, "") for key in ("groupId", "artifactId", "version")) != gav:
        raise SchemaResourceError("embedded Maven properties coordinate mismatch")


def validate_schema_archive(maven_path: str, jar_bytes: bytes) -> dict:
    """Return a deterministic member/source report, or reject without extraction."""
    gav = schema_coordinate(maven_path)
    if gav is None:
        raise SchemaResourceError("schema archive coordinate is not explicitly approved")
    if (not isinstance(jar_bytes, bytes) or len(jar_bytes) > MAX_ARCHIVE_BYTES
            or not jar_bytes.startswith(b"PK\x03\x04")):
        raise SchemaResourceError("invalid/oversized ZIP or executable archive prefix")
    group, artifact, unused = gav.split(":")
    maven_prefix = f"META-INF/maven/{group}/{artifact}/"
    members, resources, notices = [], set(), []
    embedded_pom = False
    try:
        with zipfile.ZipFile(io.BytesIO(jar_bytes)) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_MEMBERS:
                raise SchemaResourceError("empty archive or member count exceeds bound")
            end = len(jar_bytes) - len(archive.comment) - 22
            if end < 0 or jar_bytes[end:end + 4] != b"PK\x05\x06":
                raise SchemaResourceError("unexpected bytes after ZIP end record")
            seen, total = set(), 0
            for entry in entries:
                raw_name = entry.orig_filename
                name = raw_name[:-1] if entry.is_dir() else raw_name
                parts = name.split("/")
                if (len(raw_name) > 1024 or raw_name != entry.filename or not name
                        or any(part in {"", ".", ".."} or not _SEGMENT.fullmatch(part) for part in parts)):
                    raise SchemaResourceError("unsafe ZIP member path")
                key = name.casefold()
                if key in seen:
                    raise SchemaResourceError("duplicate/colliding ZIP member path")
                seen.add(key)
                mode = entry.external_attr >> 16
                kind = stat.S_IFMT(mode)
                if kind not in (0, stat.S_IFDIR if entry.is_dir() else stat.S_IFREG):
                    raise SchemaResourceError("ZIP symlink or special member is forbidden")
                if (entry.flag_bits & 1 or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        or (not entry.is_dir() and mode & 0o111)):
                    raise SchemaResourceError("encrypted, executable or unsupported ZIP member")
                total += entry.file_size
                if (entry.file_size > MAX_MEMBER_BYTES or total > MAX_TOTAL_BYTES
                        or entry.file_size > max(entry.compress_size, 1) * MAX_COMPRESSION_RATIO):
                    raise SchemaResourceError("ZIP decompression exceeds resource bounds")
                with archive.open(entry) as stream:
                    data = stream.read(MAX_MEMBER_BYTES + 1)
                if len(data) != entry.file_size or len(data) > MAX_MEMBER_BYTES:
                    raise SchemaResourceError("ZIP member length differs or exceeds bounds")
                if entry.is_dir():
                    if data:
                        raise SchemaResourceError("ZIP directory contains bytes")
                    member_kind = "directory"
                elif name in RESOURCES[gav]:
                    if name.endswith(".txt"):
                        # Only two exact GML 3.2 recipe paths have this suffix;
                        # this does not permit arbitrary text files in a capsule.
                        _text(data)
                        member_kind = "source-resource-text"
                    else:
                        root = _xml(data)
                        if name.endswith(".xsd") and root.tag != "{http://www.w3.org/2001/XMLSchema}schema":
                            raise SchemaResourceError("XSD resource root is not an XML Schema")
                        member_kind = "xml-schema" if name.endswith(".xsd") else "xml-resource"
                    resources.add(name)
                elif name == "META-INF/MANIFEST.MF":
                    _manifest(data)
                    member_kind = "inert-manifest"
                elif name == maven_prefix + "pom.xml":
                    _pom(data, gav)
                    embedded_pom = True
                    member_kind = "matching-maven-pom"
                elif name == maven_prefix + "pom.properties":
                    _properties(data, gav)
                    member_kind = "matching-maven-properties"
                elif (_NOTICE.fullmatch(parts[-1])
                      and PurePosixPath(name).suffix.lower() in {"", ".txt", ".md", ".rst", ".xml"}):
                    _xml(data) if name.endswith(".xml") else _text(data)
                    member_kind = "original-notice"
                    notices.append(name)
                else:
                    raise SchemaResourceError("unexpected executable, archive or unapproved resource member: " + name)
                member = {"path": raw_name, "kind": member_kind, "size": len(data),
                          "sha256": hashlib.sha256(data).hexdigest()}
                if name in RESOURCES[gav]:
                    member["declared_source_url"] = RESOURCES[gav][name]
                members.append(member)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error) as error:
        raise SchemaResourceError("invalid ZIP resource capsule") from error
    xsd_count = sum(name.endswith(".xsd") for name in resources)
    if not xsd_count:
        raise SchemaResourceError("resource capsule contains no actual XSD")
    missing = sorted(set(RESOURCES[gav]) - resources)
    if missing:
        raise SchemaResourceError("resource capsule omits required owned recipe paths: " + ", ".join(missing))
    return {"schema_version": 1, "gav": gav,
            "artifact_sha256": hashlib.sha256(jar_bytes).hexdigest(), "artifact_size": len(jar_bytes),
            "resource_count": len(resources), "xsd_count": xsd_count,
            "expected_resource_count": len(RESOURCES[gav]),
            "missing_resources": sorted(set(RESOURCES[gav]) - resources),
            "embedded_pom_present": embedded_pom, "members": sorted(members, key=lambda row: row["path"]),
            "notices": sorted(notices),
            "classification": "retained-source-data-candidate", "license_approval": False,
            "notice_scope": "Original XML comments and all accepted member bytes remain retained"}
