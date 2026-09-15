---
name: sast-xxe
description: "XXE (XML External Entity) injection — Java (DocumentBuilderFactory, SAX, StAX), Python (xml.etree, lxml), PHP (SimpleXML, DOMDocument), Office document processing (.docx/.xlsx), SAML responses, SVG upload, SSRF chain. CRITICAL severity."
---

# XXE — XML External Entity Injection

`OWASP: A05:2021` · `CWE-611` · Severity: CRITICAL (file read, SSRF, internal network scan)

## Java

### DocumentBuilderFactory

```java
// ❌ NEVER: default factory — external entities enabled by default
DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance()
Document doc = dbf.newDocumentBuilder().parse(userInputStream)

// ✅ ALWAYS: disable ALL external entity features
DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance()
dbf.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)
dbf.setFeature("http://xml.org/sax/features/external-general-entities", false)
dbf.setFeature("http://xml.org/sax/features/external-parameter-entities", false)
dbf.setExpandEntityReferences(false)
```

### SAXParserFactory / XMLReader

```java
// ❌ NEVER:
SAXParser sp = SAXParserFactory.newInstance().newSAXParser()
sp.parse(userInputStream, handler)

// ✅ ALWAYS:
SAXParserFactory spf = SAXParserFactory.newInstance()
spf.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)
```

### StAX XMLInputFactory

```java
// ❌ NEVER:
XMLInputFactory xif = XMLInputFactory.newInstance()

// ✅ ALWAYS:
xif.setProperty(XMLInputFactory.SUPPORT_DTD, false)
xif.setProperty(XMLInputFactory.IS_SUPPORTING_EXTERNAL_ENTITIES, false)
```

## Python

```python
# ❌ NEVER:
import xml.etree.ElementTree as ET
ET.parse(user_file)                  # vulnerable: billion-laughs + XXE

import lxml.etree as etree
parser = etree.XMLParser()           # default: resolve_entities=True
etree.fromstring(xml_data, parser)

# ✅ ALWAYS: defusedxml
from defusedxml import ElementTree
ElementTree.parse(user_file)         # safe by default

# lxml safe:
parser = etree.XMLParser(resolve_entities=False, no_network=True)
```

## PHP

```php
// ❌ NEVER:
$dom = new DOMDocument()
$dom->loadXML($userXml)              // external entities enabled

simplexml_load_string($userXml)      // same vulnerability

// ✅ ALWAYS (PHP < 8.0):
libxml_disable_entity_loader(true)
// PHP 8.0+: disabled by default — still pass LIBXML_NONET to block network
$dom->loadXML($userXml, LIBXML_NONET)
```

## Office Documents (.docx, .xlsx, .pptx)

```python
# .docx/.xlsx are ZIP archives of XML — XXE possible if XML parser has entities enabled
# ❌ Flag: raw lxml/ET parsing of Office XML extracted from user-uploaded ZIP
import zipfile
from lxml import etree
z = zipfile.ZipFile(user_file)
doc = etree.parse(z.open('word/document.xml'))   # XXE if entities enabled

# ✅ ALWAYS: use python-docx / openpyxl — they handle XML parsing safely
from docx import Document
doc = Document(user_uploaded_file)
```

## SAML Responses

```
SAML is XML-based. An attacker forges a SAML response containing:
  <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
  <samlp:Response>...<saml:Attribute>&xxe;</saml:Attribute>...

Flag: custom SAML XML parsing not using defusedxml or a maintained SAML library.
Safe: python3-saml, python-saml (post CVE-2016-1000231), ruby-saml >= 1.7.0
```

## SVG File Upload

```xml
<!-- ❌ NEVER: serve user-uploaded SVG as image/svg+xml — SVG is XML -->
<?xml version="1.0"?>
<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<svg>&xxe;</svg>

<!-- ✅ ALWAYS: sanitize with DOMPurify before serving, or convert to PNG -->
```

## SSRF Chain via XXE

```xml
<!-- XXE → SSRF: exfiltrate cloud metadata -->
<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/iam/security-credentials/role">
```

Flag XML parsers with external entity support AND no `no_network=True` / `LIBXML_NONET` as CRITICAL — both file read and AWS credential theft are possible.
