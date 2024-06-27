import streamlit as st
import os
import pandas as pd
from io import StringIO

from PIL import Image
image = Image.open("./img/sagemaker.png")
st.image(image, width=80)

version = os.environ.get("WEB_VERSION", "0.1")

st.header(f"Mammography Classification (Version {version})")
st.markdown("This is a demo for mammography exams chances of cancer")
st.markdown("_Please select an option from the sidebar_")


