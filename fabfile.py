#!/usr/bin/env python
"""

fabric-graphite is a fabric script to install Graphite, Nginx, uwsgi and all dependencies on a debian-based host.

To execute:

    * Make sure you have fabric installed on your local host (e.g. pip install fabric)
    * run `fab graphite_install -H root@{hostname}` 
      (hostname should be the name of a virtual server you're installing onto)

NOTE (tomondev, 2012-07-05): adopted to install a new site on an existing nginx, execute
fab graphite_install:site={virtualhost.com} -H {sudo_user}@{hostname}

It might prompt you for the root or sudo password on the host you are trying to instal onto.

Best to execute this on a clean virtual machine running Debian 6 (Squeeze). 
Also tested successfully on Ubuntu 12.04 VPS.

"""

from fabric.api import cd, sudo, run, put, settings

import logging
FORMAT="%(name)s %(funcName)s:%(lineno)d %(message)s"
logging.basicConfig(format=FORMAT, level=logging.INFO)

def _check_sudo():
    with settings(warn_only=True):
        result = sudo('pwd')
        if result.failed:
            print "Trying to install sudo. Must be root"
            run('apt-get update && apt-get install -y sudo')  

def graphite_install(site=''):
    """
    Installs Graphite and dependencies
    """
    _check_sudo()
    sudo('apt-get update && apt-get upgrade -y')
    sudo('apt-get install -y python-dev python-setuptools libxml2-dev libpng12-dev pkg-config build-essential supervisor')
    sudo('easy_install pip')
    sudo('pip install simplejson') # required for django admin
    sudo('pip install carbon')
    sudo('pip install whisper')
    sudo('pip install django==1.3')
    sudo('pip install django-tagging')
    sudo('pip install graphite-web')

    # creating a folder for downloaded source files
    sudo('mkdir -p /usr/local/src')
     
    # Downloading PCRE source (Required for nginx)
    with cd('/usr/local/src'):
        sudo('wget ftp://ftp.csx.cam.ac.uk/pub/software/programming/pcre/pcre-8.30.tar.gz')
        sudo('tar -zxvf pcre-8.30.tar.gz')

    # creating automatic startup scripts for carbon
    put('config/carbon', '/etc/init.d/', use_sudo=True)
    sudo('chmod ugo+x /etc/init.d/carbon')
    sudo('cd /etc/init.d && update-rc.d carbon defaults')

    # installing uwsgi from source
    with cd('/usr/local/src'):
        sudo('wget http://projects.unbit.it/downloads/uwsgi-1.2.3.tar.gz')
        sudo('tar -zxvf uwsgi-1.2.3.tar.gz')
    with cd('/usr/local/src/uwsgi-1.2.3'):
        sudo('make')

        sudo('cp uwsgi /usr/local/bin/')
        sudo('cp nginx/uwsgi_params /etc/nginx/')

        sudo('make && make install')

    # copying nginx and uwsgi configuration files
   
    put('config/nginx-site-example.conf', '/etc/nginx/sites-available/%s' % site, use_sudo=True) 
    with cd('/etc/nginx/sites-enabled'):
        sudo('ln -s ../sites-available/%s .' % site)

    put('config/uwsgi.conf', '/etc/supervisor/conf.d/', use_sudo=True)

    # installing pixman
    with cd('/usr/local/src'):
        sudo('wget http://cairographics.org/releases/pixman-0.24.4.tar.gz')
        sudo('tar -zxvf pixman-0.24.4.tar.gz')
    with cd('/usr/local/src/pixman-0.24.4'):
        sudo('./configure && make && make install')
    # installing cairo
    with cd('/usr/local/src'):
        sudo('wget http://cairographics.org/releases/cairo-1.12.2.tar.xz')
        sudo('tar -Jxf cairo-1.12.2.tar.xz')
    with cd('/usr/local/src/cairo-1.12.2'):
        sudo('./configure && make && make install')
    # installing py2cairo (python 2.x cairo)
    with cd('/usr/local/src'):
        sudo('wget http://cairographics.org/releases/py2cairo-1.8.10.tar.gz')
        sudo('tar -zxvf py2cairo-1.8.10.tar.gz')
    with cd('/usr/local/src/pycairo-1.8.10'):
        sudo('./configure --prefix=/usr && make && make install')
        sudo('echo "/usr/local/lib" > /etc/ld.so.conf.d/pycairo.conf')
        sudo('ldconfig')
    # setting the carbon config files (default)
    with cd('/opt/graphite/conf/'):
        sudo('cp carbon.conf.example carbon.conf')
        sudo('cp storage-schemas.conf.example storage-schemas.conf')
    # setting carbon pid folder and permissions
    sudo('mkdir -p /var/run/carbon')
    sudo('chown -R www-data: /var/run/carbon')

    # starting uwsgi
    sudo('supervisorctl update && supervisorctl start uwsgi')

    # starting carbon-cache
    sudo('/etc/init.d/carbon start')

    # initializing graphite django db
    with cd('/opt/graphite/webapp/graphite'):
        sudo("python manage.py syncdb")

    # changing ownership on graphite folders
    sudo('chown -R www-data: /opt/graphite/')

    # starting nginx
    sudo('/etc/init.d/nginx configtest')
    sudo('/etc/init.d/nginx reload')
