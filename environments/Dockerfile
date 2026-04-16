FROM mcr.microsoft.com/azureml/openmpi5.0-ubuntu24.04:20260322.v1

WORKDIR /

ENV CONDA_PREFIX=/azureml-envs/rca-training-env
ENV CONDA_DEFAULT_ENV=$CONDA_PREFIX
ENV PATH=$CONDA_PREFIX/bin:$PATH

# This is needed for mpi to locate libpython
ENV LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH

# Update package lists, upgrade all OS packages, and reinstall system OpenSSL & OpenSSH
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y upgrade && \
    apt-get install --reinstall -y openssl libssl-dev openssh-server libpam-runtime libc-bin dpkg-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Step 1: Create conda env with only conda-channel packages
RUN conda create -p $CONDA_PREFIX -q -y python=3.10 pip=26.0 'pandas~=1.5.3' 'scipy~=1.10.0' 'numpy~=1.22.0' -c conda-forge -c anaconda && \
    conda clean -a -y

# Step 2: Install pip packages separately (Fixes OOM issue and includes correct packages)
RUN conda run -p $CONDA_PREFIX pip install --no-cache-dir \
    azureml-defaults==1.62.0 \
    azureml-mlflow==1.62.0.post1 \
    'scikit-learn~=1.5.0' \
    'joblib~=1.2.0' \
    'matplotlib~=3.5.0' \
    xgboost==2.0.3

# Security vulnerability fixes
RUN conda run -p $CONDA_PREFIX pip install --no-cache-dir --upgrade \
    aiohttp==3.13.3 cryptography==46.0.5 'distributed>=2026.1.0'
