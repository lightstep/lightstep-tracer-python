run () {
    echo
    echo Running with python v$1
    echo
    echo
    docker run --rm -it --name exampler-runner -v `dirname $PWD`:/usr/src/myapp -w /usr/src/myapp python:$1 /bin/bash docker/_start.sh
    echo
    echo Done.
    echo
}

run 2.7.11
run 2.7.10
run 2.7.9
run 2.7.8
