
import streamlit as st
import requests
from configs import *
from PIL import Image
import boto3
from datetime import datetime


image = Image.open("./img/sagemaker.png")
st.image(image, width=80)
st.header("Mammography Image Processing")
st.caption("Using custom model from Mammography Images")



api_endpoint_url = get_parameter('resize-img-endpoint')
region_name = boto3.Session().region_name

s3 = boto3.client('s3',
                  aws_access_key_id=st.secrets.s3_credentials.access_key,
                  aws_secret_access_key=st.secrets.s3_credentials.secret_key,
                  region_name=region_name)


uploaded_file = st.file_uploader("Upload an image", type=["jpg"], accept_multiple_files=False)


if uploaded_file:

    file = uploaded_file.name.split('.')[0]
    ext = uploaded_file.name.split('.')[-1]

    filename = f"{file}-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.{ext}"
    st.image(uploaded_file.getvalue())

    if st.button("Process"):       
        with st.spinner("Wait for it..."):
            try:
                
                s3.upload_fileobj(uploaded_file, "mammo-v2-ecs-model-files", f'downloaded/original/{filename}')
                r = requests.post(api_endpoint_url, json={"filename": filename}, timeout=180)
                data = r.json()
                prediction = data["prediction"]
                st.write(prediction)

            except requests.exceptions.ConnectionError as errc:
                st.error("Error Connecting:", errc)

            except requests.exceptions.HTTPError as errh:
                st.error("Http Error:", errh)

            except requests.exceptions.Timeout as errt:
                st.error("Timeout Error:", errt)

            except requests.exceptions.RequestException as err:
                st.error("OOps: Something Else", err)

            st.success("Done!")




