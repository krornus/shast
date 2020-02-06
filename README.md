# shast

## Shell Abstract-Syntax-Tree

A basic tree parser for a subset of common shell syntax.

### Example usage
```python
ast = shast(b'echo "first line"; echo "second line"; echo "not second line" | grep -v first | sort -u > out.txt')
for grp in ast:
    print(repr(grp), repr(str(grp)))
    for cmd in grp:
        print(" ", repr(cmd), repr(str(cmd)))

        for arg in cmd.args():
            print("  ", repr(arg), repr(str(arg)))

        for redirect in cmd.redirects():
            print("  ", repr(redirect), repr(str(redirect)))
```

```
<Pipeline 0:17> 'echo "first line"'
  <Invocation 0:17> 'echo "first line"'
   <Text 0:4> 'echo'
   <Text 5:17> '"first line"'
<Pipeline 18:37> ' echo "second line"'
  <Invocation 19:37> 'echo "second line"'
   <Text 19:23> 'echo'
   <Text 24:37> '"second line"'
<Pipeline 38:97> ' echo "not second line" | grep -v first | sort -u > out.txt'
  <Invocation 39:61> 'echo "not second line"'
   <Text 39:43> 'echo'
   <Text 44:61> '"not second line"'
  <Invocation 64:77> 'grep -v first'
   <Text 64:68> 'grep'
   <Text 69:71> '-v'
   <Text 72:77> 'first'
  <Invocation 80:97> 'sort -u > out.txt'
   <Text 80:84> 'sort'
   <Text 85:87> '-u'
   <Redirect 88:97> '> out.txt'
```
