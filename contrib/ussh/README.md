# ussh: wrapper around uvt-kvm ssh

this is just a friendly wrapper around uvt-ssh, and includes in it 
behavior like in [ssh-attach](http://smoser.brickies.net/git/?p=snippits.git;a=blob;f=bash/ssh-attach;hb=HEAD)

## Why?
ussh does 2 things really

  1. passes --insecure .  This might not be right for you, but works for local system.
  1. changes the usage of ssh from `ssh command` to `ssh program [arg1 [arg2 [...]]
  
     For example of the difference see below.  ussh makes the behavior of the typed commands the same locally as on the remote system.
     
         # local command
         $ echo a b c\; echo d
         abc; echo d
         
         # through ssh
         $ ssh yourhost echo a b c\; echo d
         a b c
         d
         
         # with ussh
         $ ussh system echo a b c\; echo d
         abc; echo d
         
  
## example
When debugging and working on [bug 1493188](http://launchpad.net/bugs/1493188) I did things like this:

    name=sm-y1
    uvt-kvm create $name release=yakkety
    
    # use apt-go-fast
    ussh "$name" sh -c 'wget https://gist.githubusercontent.com/smoser/5823699/raw/b6f14a98ff0b6d7182477107ceb484bc11c285c9/apt-go-fast -O - | sudo sh'
    
    # enable proposed
    ussh $name sudo sh -c 'echo "deb http://archive.ubuntu.com/ubuntu $(lsb_release -sc)-proposed main" >/etc/apt/sources.list.d/proposed.list && apt-get update -qy'
    
    # install a package
    ussh $name sudo apt-get install -qy overlayroot
    
    # enable overlayroot without recurse
    ussh "$name" sh -c 'echo overlayroot=tmpfs:recurse=0 | sudo tee /etc/overlayroot.local.conf'
    
    # install a deb from stdin
    ussh "$name" sh -c 'f=/tmp/my.deb; cat >$f; sudo dpkg -i $f; rm -f $f' < /tmp/overlayroot_0.28ubuntu2_all.deb
    ussh "$name" sudo reboot
    ussh "$name"
    ussh "$name" sudo sh -xc 'mkfs.ext4 -F /dev/vdb && echo /dev/vdb /mnt auto defaults 0 0 >> /etc/fstab && mount /mnt && echo hi mom > /mnt/hello.txt && echo manual_cache_clean: true > /etc/cloud/cloud.cfg.d/sm.cfg'
    ussh "$name" sh -c 'echo overlayroot=tmpfs:recurse=1 | sudo tee /etc/overlayroot.local.conf'

    # disable overlayroot
    ussh sm-y1 sudo overlayroot-chroot rm /etc/overlayroot.local.conf
    echo "root:passw0rd" | ussh "$name" sudo chpasswd