# Councils in Action

[![CI](https://github.com/PugetSoundClinic-PIT/councils-in-action/actions/workflows/ci.yml/badge.svg)](https://github.com/PugetSoundClinic-PIT/councils-in-action/actions/workflows/ci.yml)

This repository stores the files needed for [quarto](https://quarto.org/) to generate our paper "Councils in Action ... TODO"

View the rendered article at: [https://PugetSoundClinic-PIT.github.io/councils-in-action/](https://PugetSoundClinic-PIT.github.io/councils-in-action/)

## Abstract

TODO

---

## Development Commands

```
just --list
Available recipes:
    build   # build page
    clean   # remove build files
    default # list all available commands
    setup name="councils-in-action" # create conda env and install all deps
    watch   # watch file, build, and serve
```

### Dev Setup

1. Install [Quarto](https://quarto.org/docs/get-started/).
2. Install [Just](https://github.com/casey/just#packages).
3. Run `just setup` to create a new conda environment with all dependencies.
4. Run `conda activate councils-in-action` to activate the environment.
5. Build!
    - `just build` to build the project to the `_build/` folder.
    - `just watch` to watch this directory and build just the website on file save.


You may run into issues running your first `just build` command. If the issue relates to
`tinytex` or `texlive` then try installing the latest versions:

* Install:
`sudo apt-get install texlive-xetex texlive-fonts-recommended texlive-plain-generic`
* Or Upgrade:
`sudo apt-get upgrade texlive-xetex texlive-fonts-recommended texlive-plain-generic`
