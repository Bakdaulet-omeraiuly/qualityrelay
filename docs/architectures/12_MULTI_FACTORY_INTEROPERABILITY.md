# Industrial Data, Supplier Boundaries, Digital Thread

**Owner:** adilnurgg + 4th engineer  
**Status:** research design + partial reference implementation; see status below.

## Scale path
Factory -> line -> workcell -> station -> event -> specimen -> lot -> CAD revision. Integrate CAD/STL, CSV caliper records, QMS results, PLC/MES/ERP read-only adapters, RTSP camera events, and OPC UA/MQTT where specifically authorized. Keep event identifiers stable across systems.

## Contract governance
Document schema version, decimal units, timezone, origin, privacy labels and nominal tolerances per part revision. Cross-factory supplier agents share only approved quality summary; no raw vendor bill of materials, private camera frames or fabrication recipes without an agreement. Support temporal view of design -> plan -> execution -> inspection.

## Fallback and rollout
Offline local inspection must continue in bounded HOLD mode; factory federation is optional. Site integration begins with read-only shadow mode, followed by test-only approvals and then tightly supervised action. Do not market as plug-and-play into unknown safety-critical manufacturing lines.

## Validation
Test wrong-unit conversions, stale CAD rev, same serial from two suppliers, duplicated dispatch, lost reconciliation events, cross-tenant access, timezone drift and incompatible ontology. Track integration labor as part of ROI.

