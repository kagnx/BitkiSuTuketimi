# -*- coding: utf-8 -*-
"""pytest kök dizinini sys.path'e ekler (app paketi içe aktarılabilsin)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
