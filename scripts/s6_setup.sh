cd /home/centos

if [[ ! -d /home/centos/skalibs/.git ]]
	then
		git clone git://git.skarnet.org/skalibs
		cd skalibs && ./configure && make && sudo make install && cd -
fi

if [[ ! -d /home/centos/execline/.git ]]
	then
		git clone git://git.skarnet.org/execline
		cd execline && ./configure && make && sudo make install && cd -
fi

if [[ ! -d /home/centos/s6/.git ]]
	then
		git clone https://github.com/skarnet/s6.git
		cd s6 && ./configure && make && sudo make install && cd -
fi

cd -