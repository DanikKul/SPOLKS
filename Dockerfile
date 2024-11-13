FROM ubuntu:18.04

RUN apt-get update && apt-get install -y openssh-server
RUN mkdir /var/run/sshd

RUN adduser --disabled-password --gecos "" worker
RUN echo 'worker ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

RUN passwd -d worker

ENV USER worker
ENV HOME /home/$USER
ENV MPI_DIR=/opt/ompi
ENV PATH="$MPI_DIR/bin:$HOME/.local/bin:$PATH"
ENV LD_LIBRARY_PATH="$MPI_DIR/lib:$LD_LIBRARY_PATH"
WORKDIR $HOME

RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd

RUN apt-get -q update \
    && apt-get install -y \
    python3 python3-dev python3-pip \
    gcc gfortran binutils \
    && pip3 install --upgrade pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ADD https://download.open-mpi.org/release/open-mpi/v5.0/openmpi-5.0.5.tar.bz2 .
RUN tar xf openmpi-5.0.5.tar.bz2 \
    && cd openmpi-5.0.5 \
    && ./configure \
    && make -j4 all \
    && make install \
    && cd .. && rm -rf \
    openmpi-5.0.5 openmpi-5.0.5.tar.bz2 /tmp/*

RUN  apt-get update \
  && apt-get install -y git

RUN apt install zlib1g-dev

ENV NOTVISIBLE "in users profile"
RUN echo "export VISIBLE=now" >> /etc/profile

RUN pip3 install setuptools
RUN pip3 install mpi4py
RUN pip3 install numpy

RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed -i 's/#PermitEmptyPasswords no/PermitEmptyPasswords yes/' /etc/ssh/sshd_config
RUN sed -i 's/#PermitEmptyPasswords yes/PermitEmptyPasswords yes/' /etc/ssh/sshd_config
RUN sed -i 's/#UsePAM yes/UsePAM no/' /etc/ssh/sshd_config
RUN sed -i 's/UsePAM yes/UsePAM no/' /etc/ssh/sshd_config
RUN sed -i 's/#UsePAM no/UsePAM no/' /etc/ssh/sshd_config

USER $USER

RUN git clone https://github.com/DanikKul/SPOLKS.git

USER root

EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]