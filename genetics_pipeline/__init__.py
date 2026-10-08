"""Genetic Correlates Explorer build pipeline (gce).

Reads the flat-file tables under data/genetics/, resolves ontology terms and
grades against live sources, computes the cross-phenotype matrix, and emits
the static site under genetics/. See scripts/Genetic Correlates Explorer —
Build Spec.docx sections 5-7 for the data model and module contract this
package implements.
"""
