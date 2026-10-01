from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)
CONFIG_DIR = Path(__file__).resolve().parent / "data" / "construction_types"

SAME_DOMAIN_GROUPS = [
    {"Industrial", "Factory"},
    {"Commercial", "Mall / Shopping Center"},
]


class ConstructionTypeEngine:
    """
    Multi-signal, explainable, and configurable engine to automatically detect
    construction types from DWG/DXF drawings.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or CONFIG_DIR
        self.master_config: dict[str, Any] = {}
        self.category_configs: dict[str, dict[str, Any]] = {}
        self.load_configurations()

    def load_configurations(self) -> None:
        master_file = self.config_dir / "detection_config.json"
        if master_file.exists():
            try:
                self.master_config = json.loads(master_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"Failed to load detection_config.json: {e}")

        if not self.master_config:
            self.master_config = {
                "weights": {"text": 0.35, "layer": 0.25, "geometry": 0.20, "elements": 0.10, "spatial": 0.10},
                "thresholds": {"high_confidence": 0.80, "medium_confidence": 0.60, "min_detection_confidence": 0.35},
                "mixed_use": {"enabled": True, "min_component_score": 0.35, "score_ratio_threshold": 0.70},
                "defaults": {
                    "unknown_type": "Other / Unknown",
                    "insufficient_evidence_message": "Construction type could not be determined with high confidence due to insufficient drawing evidence."
                }
            }

        for p in self.config_dir.glob("*.json"):
            if p.name == "detection_config.json":
                continue
            try:
                cat_data = json.loads(p.read_text(encoding="utf-8"))
                cat_name = cat_data.get("name")
                if cat_name:
                    self.category_configs[cat_name] = cat_data
            except Exception as e:
                logger.error(f"Failed to load category rule {p.name}: {e}")

    def detect_construction_type(self, drawing_data: dict[str, Any]) -> dict[str, Any]:
        weights = self.master_config.get("weights", {})
        w_text = weights.get("text", 0.35)
        w_layer = weights.get("layer", 0.25)
        w_geo = weights.get("geometry", 0.20)
        w_elem = weights.get("elements", 0.10)
        w_spatial = weights.get("spatial", 0.10)

        thresholds = self.master_config.get("thresholds", {})
        high_th = thresholds.get("high_confidence", 0.80)
        med_th = thresholds.get("medium_confidence", 0.60)
        min_th = thresholds.get("min_detection_confidence", 0.35)

        raw_texts = self._extract_drawing_texts(drawing_data)
        raw_layers = drawing_data.get("layers", [])
        raw_elements = drawing_data.get("elements", [])
        raw_entities = drawing_data.get("entities", [])

        category_scores: dict[str, float] = {}
        category_evidence: dict[str, list[str]] = {}
        category_subtypes: dict[str, str] = {}
        total_signals_detected = 0

        for cat_name, cat_rule in self.category_configs.items():
            if cat_name == "Mixed Use":
                continue

            text_score, text_ev = self._evaluate_text_signal(raw_texts, cat_rule)
            layer_score, layer_ev = self._evaluate_layer_signal(raw_layers, cat_rule)
            geo_score, geo_ev = self._evaluate_geometry_signal(drawing_data, cat_rule)
            elem_score, elem_ev = self._evaluate_element_signal(raw_elements, cat_rule)
            spatial_score, spatial_ev = self._evaluate_spatial_signal(drawing_data, cat_rule)

            combined_score = (
                w_text * text_score
                + w_layer * layer_score
                + w_geo * geo_score
                + w_elem * elem_score
                + w_spatial * spatial_score
            )

            all_ev = text_ev + layer_ev + geo_ev + elem_ev + spatial_ev
            if all_ev:
                total_signals_detected += len(all_ev)

            category_scores[cat_name] = round(combined_score, 4)
            category_evidence[cat_name] = all_ev
            category_subtypes[cat_name] = self._determine_subtype(raw_texts, cat_rule)

        sorted_cats = sorted(category_scores.items(), key=lambda kv: kv[1], reverse=True)
        top_cat, top_score = sorted_cats[0] if sorted_cats else ("Other / Unknown", 0.0)
        second_cat, second_score = sorted_cats[1] if len(sorted_cats) > 1 else ("", 0.0)

        now_iso = datetime.now(timezone.utc).isoformat()

        if top_score < min_th or total_signals_detected < 2 or not raw_entities:
            return {
                "construction_type": "Other / Unknown",
                "subtype": "General / Unspecified",
                "confidence": round(max(top_score, 0.05), 2),
                "confidence_level": "Low",
                "scores": {k: round(v, 2) for k, v in category_scores.items()},
                "evidence": ["Insufficient CAD metadata or text annotations to reliably determine construction type."],
                "components": [],
                "classification_source": "ai",
                "classification_reason": "Construction type could not be determined with high confidence due to insufficient drawing evidence.",
                "classification_timestamp": now_iso,
                "status": "NEEDS_REVIEW",
            }

        # Check for Mixed-Use Projects across different functional domains
        mixed_config = self.master_config.get("mixed_use", {})
        min_comp = mixed_config.get("min_component_score", 0.35)
        ratio_th = mixed_config.get("score_ratio_threshold", 0.70)

        is_same_domain = any({top_cat, second_cat}.issubset(grp) for grp in SAME_DOMAIN_GROUPS)

        is_mixed_use = False
        components = []
        if (
            mixed_config.get("enabled", True)
            and not is_same_domain
            and second_score >= min_comp
            and top_score > 0
            and (second_score / top_score) >= ratio_th
            and top_cat != second_cat
        ):
            is_mixed_use = True
            sum_scores = top_score + second_score
            p1 = round((top_score / sum_scores) * 100)
            p2 = 100 - p1
            components = [
                {"type": top_cat, "percentage": p1, "subtype": category_subtypes.get(top_cat, "")},
                {"type": second_cat, "percentage": p2, "subtype": category_subtypes.get(second_cat, "")},
            ]

        if is_mixed_use:
            final_type = "Mixed Use"
            subtype = f"{top_cat} + {second_cat}"
            confidence = round(min(0.92, (top_score + second_score) / 2.0), 2)
            evidence = category_evidence[top_cat][:3] + category_evidence[second_cat][:3]
            evidence.insert(0, f"Dual occupancy detected: {p1}% {top_cat} and {p2}% {second_cat}")
        else:
            final_type = top_cat
            subtype = category_subtypes.get(top_cat, self.category_configs.get(top_cat, {}).get("default_subtype", "Standard"))
            confidence = round(min(0.98, top_score), 2)
            evidence = category_evidence[top_cat]

        if confidence >= high_th:
            confidence_level = "High"
            status = "HIGH_CONFIDENCE"
        elif confidence >= med_th:
            confidence_level = "Medium"
            status = "MEDIUM_CONFIDENCE"
        else:
            confidence_level = "Low"
            status = "NEEDS_REVIEW"

        reason = (
            f"{confidence_level} confidence detection based on {len(evidence)} verified CAD signals: "
            f"{evidence[0] if evidence else 'drawing patterns'}."
        )

        return {
            "construction_type": final_type,
            "subtype": subtype,
            "confidence": confidence,
            "confidence_level": confidence_level,
            "scores": {k: round(v, 2) for k, v in category_scores.items()},
            "evidence": evidence,
            "components": components,
            "classification_source": "ai",
            "classification_reason": reason,
            "classification_timestamp": now_iso,
            "status": status,
        }

    def _extract_drawing_texts(self, drawing_data: dict[str, Any]) -> list[str]:
        raw_set: set[str] = set()
        for s in drawing_data.get("texts", []):
            if isinstance(s, dict):
                val = s.get("raw_text") or s.get("material_description") or s.get("text")
                if val:
                    val_str = str(val).strip()
                    if val_str:
                        raw_set.add(val_str)
            elif isinstance(s, str) and s.strip():
                raw_set.add(s.strip())

        for e in drawing_data.get("entities", []):
            t = e.get("text") if isinstance(e, dict) else getattr(e, "text", None)
            if t:
                t_str = str(t).strip()
                if t_str:
                    raw_set.add(t_str)

        return list(raw_set)

    def _evaluate_text_signal(self, texts: list[str], rule: dict[str, Any]) -> tuple[float, list[str]]:
        if not texts:
            return 0.0, []

        keywords = [kw.lower() for kw in rule.get("keywords", []) if kw]
        if not keywords:
            return 0.0, []

        matched_counts: dict[str, int] = {}
        for txt in texts:
            t_low = txt.lower()
            for kw in keywords:
                if kw in t_low and re.search(r"\b" + re.escape(kw) + r"\b", t_low):
                    matched_counts[kw] = matched_counts.get(kw, 0) + 1

        if not matched_counts:
            return 0.0, []

        unique_matches = len(matched_counts)
        total_occurrences = sum(matched_counts.values())

        score = min(1.0, (unique_matches * 0.22) + min(0.30, total_occurrences * 0.05))

        evidence = []
        for kw, cnt in sorted(matched_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]:
            evidence.append(f"{cnt} '{kw.title()}' label{'s' if cnt > 1 else ''} detected")

        return score, evidence

    def _evaluate_layer_signal(self, layers: list[str], rule: dict[str, Any]) -> tuple[float, list[str]]:
        if not layers:
            return 0.0, []

        patterns = rule.get("layer_patterns", [])
        matched_layers: list[str] = []
        for l in layers:
            l_str = str(l).strip()
            for pat in patterns:
                if re.match(pat, l_str, re.IGNORECASE):
                    matched_layers.append(l_str)
                    break

        if not matched_layers:
            return 0.0, []

        score = min(1.0, 0.50 + (len(matched_layers) * 0.15))
        sample_layers = ", ".join(matched_layers[:3])
        evidence = [f"{rule.get('name')} specific CAD layers identified ({sample_layers})"]
        return score, evidence

    def _evaluate_geometry_signal(self, drawing_data: dict[str, Any], rule: dict[str, Any]) -> tuple[float, list[str]]:
        geo_profile = rule.get("geometry_profile", {})
        if not geo_profile:
            return 0.0, []

        elements = drawing_data.get("elements", [])
        rooms = [el for el in elements if (el.get("element_type") if isinstance(el, dict) else getattr(el, "element_type", "")) in {"ROOM", "FLOOR"}]
        columns = [el for el in elements if (el.get("element_type") if isinstance(el, dict) else getattr(el, "element_type", "")) == "COLUMN"]

        evidence = []
        score = 0.35

        if rooms:
            areas = []
            for r in rooms:
                geo = r.get("geometry", {}) if isinstance(r, dict) else getattr(r, "geometry", {})
                if geo.get("area"):
                    areas.append(float(geo["area"]))
            avg_area = sum(areas) / len(areas) if areas else 0.0
            min_a = geo_profile.get("avg_room_area_min", 0.0)
            max_a = geo_profile.get("avg_room_area_max", 9999.0)

            if min_a <= avg_area <= max_a:
                score += 0.40
                evidence.append(f"Room area distribution (~{round(avg_area, 1)} m?) aligns with {rule.get('name')} standards")

        if columns and "column_span_min" in geo_profile:
            score += 0.20
            evidence.append(f"Structural column framework detected with spans compatible with {rule.get('name')}")

        return min(1.0, score), evidence

    def _evaluate_element_signal(self, elements: list[Any], rule: dict[str, Any]) -> tuple[float, list[str]]:
        if not elements:
            return 0.0, []

        indicators = rule.get("element_indicators", [])
        detected_types = set()
        detected_subtypes = set()
        for el in elements:
            if isinstance(el, dict):
                detected_types.add(el.get("element_type"))
                detected_subtypes.add(el.get("subtype"))
            else:
                detected_types.add(getattr(el, "element_type", ""))
                detected_subtypes.add(getattr(el, "subtype", ""))

        all_types = detected_types.union(detected_subtypes)
        matches = [ind for ind in indicators if ind in all_types]
        if not matches:
            return 0.0, []

        score = min(1.0, 0.45 + (len(matches) * 0.20))
        evidence = [f"Detected elements consistent with {rule.get('name')} ({', '.join(matches[:3])})"]
        return score, evidence

    def _evaluate_spatial_signal(self, drawing_data: dict[str, Any], rule: dict[str, Any]) -> tuple[float, list[str]]:
        elements = drawing_data.get("elements", [])
        doors = [el for el in elements if (el.get("element_type") if isinstance(el, dict) else getattr(el, "element_type", "")) == "DOOR"]
        windows = [el for el in elements if (el.get("element_type") if isinstance(el, dict) else getattr(el, "element_type", "")) == "WINDOW"]

        cat_name = rule.get("name", "")
        evidence = []
        score = 0.30

        if cat_name in {"Residential", "Hotel / Resort"} and len(doors) >= 2 and len(windows) >= 2:
            score += 0.50
            evidence.append(f"Frequent fenestration pattern ({len(doors)} doors, {len(windows)} windows) typical of compartmentalized occupancy")
        elif cat_name in {"Factory", "Industrial", "Warehouse"} and len(doors) <= 2 and len(elements) > 2:
            score += 0.50
            evidence.append("Open floor spatial envelope with minimal interior partition subdivison")

        return min(1.0, score), evidence

    def _determine_subtype(self, texts: list[str], rule: dict[str, Any]) -> str:
        subtypes = rule.get("subtypes", [])
        if not subtypes:
            return "Standard"

        text_blob = " ".join(texts).lower()
        for st in subtypes:
            tokens = [t.lower() for t in re.split(r"[/+\s-]", st) if len(t) > 3]
            if any(tok in text_blob for tok in tokens):
                return st

        return rule.get("default_subtype", subtypes[0])

    def get_type_rules(self, construction_type: str) -> dict[str, Any]:
        cfg = self.category_configs.get(construction_type)
        if cfg:
            return cfg.get("boq_rules", {})
        return {}
