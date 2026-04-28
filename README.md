# build-paper GitHub action

GitHub action to build a ipynb into a PDF and a static GitHub page

## Inputs

### `filename`
 **Required** The name of the file to build. Default `"paper.ipynb"`

 ## Outputs

### `time`

The time it took to run the build

## Example use

```yaml
uses: vln-devsecops/actions-build-paper@v1
with:
    filename: somename.ipynb
```

## Building the action
```
npm i -g @vercel/ncc
npm run build
```
