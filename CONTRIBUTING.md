# Contributing

Thank you for your interest in helping out with this project.

Two very straighforward ways of getting involved are:

* Issues
    * looking at [issues raised](https://github.com/ha-warmup/warmup/issues) and trying to advise users looking for help, or encouraging them to obtain useful diagnostics
* Documentation
    * increasing the detail, accuracy or readability in our [documentation wiki](https://github.com/ha-warmup/warmup/wiki)

If you want to take things further you can get involved with code, 
either to deal with issues raised or to develop new features. 

## Development

As you will use a fork for your development we encourage you to 
familiarise yourself with the [Github guide to working with forks](https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/working-with-forks).
    
All development work should be done on branches created from the **dev** branch. 
Please ensure you understand [the branching model we follow](https://nvie.com/posts/a-successful-git-branching-model/).

Both of the above-linked guides also include command examples for you 
to work on your local project repository. 

Please raise an issue if you want further guidance on developing new features or fixing issues.

Once you have completed your development and testing on your changes, 
then please raise a Pull Request for us to be able to merge in your work. They should be merged into the **dev** branch.

### Project Structure

For the time being, contributors have settled on a 
[project structure](https://github.com/ha-warmup/warmup/issues/50) 
that includes:

* HACS integration as a custom repository, with associated metadata files
* Instructions for manual install as custom_component
* incorporating any changes to the API-related python code in warmup4ie subfolder
	* and keeping a tracking copy in the root warmup4ie-PyPi folder for later


## Release

We use GitHub Releases as good practice, both for a github repo, and for a [HACS integration](https://hacs.xyz/docs/publish/integration/#github-releases-optional).

Before bringing changes into the **master** branch, please ensure that you have referenced the changes into [CHANGELOG.md](CHANGELOG.md) on dev. You could use `git show --oneline` to gather the info.

When releasing a version, please ensure that you update the version in 

```
custom_components/warmup/manifest.json
```

You may find it convenient to tag your release candidate. Since 2021.5.23, the versioning format has been YYYY.M.D (no leading zeroes). When raising the PR from your dev to the main project master, remember to ask for a new Github Releases to be created with the same tag.


