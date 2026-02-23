#!/usr/bin/env python3
"""
Diagnostic script to debug blank image generation from .note files.
Usage: uv run python scripts/debug_note.py <path_to_note_file>
"""

import sys
import os
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import sn2md.supernotelib as sn
from sn2md.supernotelib.converter import ImageConverter, VisibilityOverlay, build_visibility_overlay

def diagnose(note_path: str):
    print(f"\n{'='*60}")
    print(f"DIAGNOSING: {note_path}")
    print(f"{'='*60}\n")

    # 1. Load the notebook
    print("[1] Loading notebook...")
    try:
        notebook = sn.load_notebook(note_path)
    except Exception as e:
        print(f"  ❌ FAILED to load notebook: {e}")
        return
    print(f"  ✅ Loaded successfully")
    print(f"     Type: {notebook.get_type()}")
    print(f"     Signature: {notebook.get_signature()}")
    print(f"     Dimensions: {notebook.get_width()} x {notebook.get_height()}")
    print(f"     Total pages: {notebook.get_total_pages()}")
    print(f"     Supports highres grayscale: {notebook.supports_highres_grayscale()}")

    # 2. Check each page
    total_pages = notebook.get_total_pages()
    converter = ImageConverter(notebook)
    bg_visibility = VisibilityOverlay.DEFAULT
    vo = build_visibility_overlay(background=bg_visibility)

    for page_num in range(total_pages):
        print(f"\n[Page {page_num}] {'─'*40}")
        page = notebook.get_page(page_num)

        # Layer support
        layer_supported = page.is_layer_supported()
        print(f"  Layer supported: {layer_supported}")

        if not layer_supported:
            content = page.get_content()
            print(f"  Content: {'present (' + str(len(content)) + ' bytes)' if content else '❌ NONE'}")
            protocol = page.get_protocol()
            print(f"  Protocol: {protocol}")
        else:
            # Layer details
            layers = page.get_layers()
            print(f"  Number of layers: {len(layers)}")
            print(f"  Orientation: {page.get_orientation()}")
            print(f"  Style: {page.get_style()}")
            
            # Layer order
            layer_order = page.get_layer_order()
            print(f"  Layer order (LAYERSEQ): {layer_order}")
            if not layer_order:
                print(f"  ⚠️  WARNING: Empty layer order! This will produce a BLANK image.")

            # Layer info / visibility
            layer_info_raw = page.metadata.get('LAYERINFO')
            print(f"  LAYERINFO raw: {layer_info_raw[:100] if layer_info_raw else 'None'}...")

            # Get visibility (same logic as converter)
            try:
                from sn2md.supernotelib.converter import ImageConverter as IC
                temp_converter = IC(notebook)
                from sn2md.supernotelib import utils
                wrapped_page = utils.WorkaroundPageWrapper.from_page(page)
                visibility = temp_converter._get_layer_visibility(wrapped_page)
                print(f"  Layer visibility: {visibility}")
                
                # Check if all visible layers are empty
                all_invisible = True
                for name, is_visible in visibility.items():
                    if is_visible:
                        all_invisible = False
                if all_invisible:
                    print(f"  ⚠️  WARNING: All layers are INVISIBLE! This will produce a BLANK image.")
            except Exception as e:
                print(f"  ⚠️  Could not get visibility: {e}")

            for i, layer in enumerate(layers):
                name = layer.get_name()
                content = layer.get_content()
                layer_type = layer.get_type()
                protocol = layer.get_protocol()
                content_info = f"present ({len(content)} bytes)" if content else "❌ NONE"
                visible_info = visibility.get(name, "unknown") if 'visibility' in dir() else "?"
                print(f"    Layer {i}: name={name}, type={layer_type}, protocol={protocol}, content={content_info}, visible={visible_info}")

        # Try to actually convert the page
        print(f"\n  Attempting conversion...")
        try:
            img = converter.convert(page_num, vo)
            print(f"  ✅ Conversion succeeded: size={img.size}, mode={img.mode}")
            
            # Check if the image is blank
            from PIL import ImageStat
            stat = ImageStat.Stat(img.convert('L'))
            mean_brightness = stat.mean[0]
            min_val = stat.extrema[0][0]
            max_val = stat.extrema[0][1]
            print(f"     Brightness: mean={mean_brightness:.1f}, min={min_val}, max={max_val}")
            
            if min_val == max_val:
                print(f"  ⚠️  WARNING: Image is COMPLETELY UNIFORM (solid color = {min_val}). Content is blank!")
            elif mean_brightness > 250:
                print(f"  ⚠️  WARNING: Image is nearly all white (mean brightness {mean_brightness:.1f}).")
            else:
                print(f"  ✅ Image contains visible content.")

            # Save diagnostic image
            diag_dir = os.path.join(os.path.dirname(note_path), "_debug")
            os.makedirs(diag_dir, exist_ok=True)
            diag_path = os.path.join(diag_dir, f"page_{page_num}.png")
            img.save(diag_path, format="PNG")
            print(f"     Saved diagnostic image to: {diag_path}")

        except Exception as e:
            print(f"  ❌ Conversion FAILED: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("DIAGNOSIS COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/debug_note.py <path_to_note_file>")
        sys.exit(1)
    diagnose(sys.argv[1])
